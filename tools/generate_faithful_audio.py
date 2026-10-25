"""Un passage de conte fidèle : palette approuvée, paroles vérifiées et silence initial.

Par défaut, seul le premier passage du Roi-grenouille est produit.
"""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

from audio.tts_batch import (Batch, PCM, atomic_json, atomic_wave, batch_lock, digest,
                            file_hash, read_wave, receipt_matches, write_receipt)
from engine.book_engine import BookEngine
from engine.content import Content, ROOT

PALETTE = ROOT / 'audio/emotion_profiles.json'
ASR_DIR = ROOT / 'audio/experiments/emotions/asr_cache/models--Systran--faster-whisper-small/snapshots/536b0662742c02347bc0e980a01041f333bce120'


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--book', default='roi_grenouille')
    result.add_argument('--segment', type=int, default=1)
    result.add_argument('--choice', type=int, choices=(1,2), default=1)
    result.add_argument('--voice', type=Path, default=ROOT/'chatterbox/Recording.wav')
    result.add_argument('--output-dir', type=Path, default=ROOT/'audio/experiments/roi_grenouille/files')
    result.add_argument('--cache-dir', type=Path, default=ROOT/'audio/experiments/roi_grenouille/cache')
    result.add_argument('--report', type=Path, default=ROOT/'reports/roi_grenouille/audio_premier_segment.json')
    result.add_argument('--asr-model-dir', type=Path, default=ASR_DIR)
    result.add_argument('--chunk-chars', type=int, default=300)
    result.add_argument('--pause-ms', type=int, default=150)
    result.add_argument('--lead-in-ms', type=int, default=1000)
    result.add_argument('--seed', type=int, default=20261018)
    result.add_argument('--threads', type=int, default=8)
    result.add_argument('--attempts', type=int, default=3)
    result.add_argument('--dry-run', action='store_true')
    return result


def normalize(text):
    return ' '.join(text.split())


def plan_segment(args, content=None):
    content = content or Content()
    engine = BookEngine(content, args.book)
    if not 1 <= args.segment <= len(engine.book['scenes']):
        raise ValueError('Numéro de passage hors du conte.')
    for _ in range(args.segment-1):
        engine.choose(args.choice-1)
        engine.advance()
    # Garder le plan historique compatible avec le générateur courant,
    # notamment l'annonce du titre et ses consignes de prononciation.
    from tools.generate_story_audio import plan_current
    plan = plan_current(engine,args,Content.read(PALETTE))
    plan['lead_in_ms'] = args.lead_in_ms
    return plan


def assemble(parts, lead_in_ms, pause_ms):
    if not parts or not 0 <= lead_in_ms <= 5000 or not 0 <= pause_ms <= 3000:
        raise ValueError('Assemblage ou pauses invalides.')
    rate = parts[0].sample_rate
    if any(p.sample_rate != rate for p in parts):
        raise ValueError('Fréquences différentes entre les prises.')
    prefix = b'\0\0' * (rate*lead_in_ms//1000)
    gap = b'\0\0' * (rate*pause_ms//1000)
    return PCM(rate, prefix+gap.join(p.frames for p in parts))


def main(argv=None):
    args = parser().parse_args(argv)
    if not 1 <= args.threads <= 32 or not 1 <= args.attempts <= 10:
        raise ValueError('Nombre de threads ou de tentatives invalide.')
    if not 0 <= args.lead_in_ms <= 5000 or not 0 <= args.pause_ms <= 3000:
        raise ValueError('Pause invalide.')
    plan = plan_segment(args)
    atomic_json(args.report, plan)
    print(json.dumps(plan,ensure_ascii=False,indent=2),flush=True)
    if args.dry_run:
        return 0
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    sys.path.insert(0,str(ROOT/'tmp/emotions_asr_deps'))
    import torch
    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(1)
    from audio.chatterbox_backend import ChatterboxBackend, environment_identity, prepare_model
    from audio.speech_verification import IncompleteSpeech, SpeechVerifier, prepare_asr
    started = time.monotonic()
    with batch_lock(args.cache_dir/'.story.lock'), batch_lock(args.output_dir/'.story-output.lock'):
        revision = Content.read(ROOT/'audio/experiments/passeuse_ch1/cache/model_revision.json')
        if not (args.cache_dir/'model_revision.json').is_file():
            atomic_json(args.cache_dir/'model_revision.json',revision)
        model_dir, model = prepare_model(args.cache_dir)
        environment = environment_identity()
        voice_sha = file_hash(args.voice)
        reference = args.cache_dir/'references'/(voice_sha+'.wav')
        reference.parent.mkdir(parents=True,exist_ok=True)
        if not reference.is_file() or file_hash(reference) != voice_sha:
            temporary = reference.with_suffix('.wav.partial')
            shutil.copyfile(args.voice,temporary)
            if file_hash(temporary) != voice_sha:
                raise ValueError('La référence a changé pendant sa copie.')
            os.replace(temporary,reference)
        asr_dir, asr_identity = prepare_asr(args.cache_dir,model_dir=args.asr_model_dir)
        profile = digest(dict(plan=plan,voice=voice_sha,model=model,environment=environment,
                              threads=args.threads,pipeline='faithful-styled-v1'))
        identity = digest(dict(profile=profile,text=plan['text'],segment_id=plan['segment_id']))
        target = Path(plan['output_file'])
        if receipt_matches(target,identity):
            existing = Content.read(Path(str(target)+'.json'))
            if existing.get('verification',{}).get('passed'):
                print('Premier passage déjà vérifié : conservé.',flush=True)
                plan.update(status='ready',profile=profile,voice_sha256=voice_sha,
                            verification=existing['verification'],seconds=existing['seconds'])
                atomic_json(args.report,plan)
                return 0
        if target.exists():
            raise ValueError('Un autre profil occupe déjà ce nom de WAV ; employer un autre dossier de sortie.')
        plan.update(voice_sha256=voice_sha,profile=profile,model=model,environment=environment,
                    status='generating',verification_policy=digest(asr_identity))
        atomic_json(args.report,plan)
        backend = None
        verifier = None

        def shared_verifier():
            nonlocal verifier
            if verifier is None:
                verifier = SpeechVerifier(asr_dir)
            return verifier

        parts = []
        for number, span in enumerate(plan['spans'],1):
            parameters = span['parameters']
            def factory():
                nonlocal backend
                if backend is None:
                    print('Chargement unique de Chatterbox Multilingual V3...',flush=True)
                    backend = ChatterboxBackend(model_dir,reference,'cpu',parameters)
                backend.parameters = parameters
                return backend
            recipe = dict(voice_sha256=voice_sha,language='fr',model=model,environment=environment,
                          device='cpu',parameters=parameters,torch_threads=args.threads,
                          palette_sha256=plan['palette_sha256'])
            batch = Batch(args.cache_dir,recipe,factory,max_chars=args.chunk_chars,pause_ms=args.pause_ms,
                          seed=args.seed,attempts=args.attempts,splitter='linguistic-v1',
                          verifier_factory=shared_verifier,verifier_identity=asr_identity)
            span_id = digest(dict(text=span['text'],profile=batch.profile))
            component = args.cache_dir/batch.profile/'components'/(span_id+'.wav')
            record = dict(segment_id=span_id,scene_id=plan['scene_id'],text=span['text'],target=component)
            print(f"\nVoix {number}/{len(plan['spans'])} | {span['speaker']} | {span['emotion']}",flush=True)
            stats = batch.run([record])
            if stats['failed']:
                plan.update(status='failed',failed_span=number)
                atomic_json(args.report,plan)
                raise RuntimeError('Passage vocal refusé ; les prises vérifiées restent en cache pour la reprise.')
            pcm = read_wave(component)
            parts.append(pcm)
            span.update(component=str(component),sha256=file_hash(component),profile=batch.profile,
                        seconds=round(len(pcm.frames)/2/pcm.sample_rate,3),stats=stats)
            atomic_json(args.report,plan)
        pcm = assemble(parts,args.lead_in_ms,args.pause_ms)
        print('\nContrôle du segment complet, narration et deux choix compris...',flush=True)
        try:
            # Le fichier long inclut l'amorce et plusieurs pauses. Retirer les
            # silences de l'analyse ASR évite les hallucinations de sous-titres ;
            # le WAV lui-même reste intact et les critères de paroles identiques.
            check = shared_verifier().verify(plan['text'],pcm,vad_filter=True)
        except IncompleteSpeech as exc:
            rejected = args.cache_dir/plan['profile']/'rejected_full_segment.wav'
            atomic_wave(rejected,pcm)
            atomic_json(Path(str(rejected)+'.json'),dict(sha256=file_hash(rejected),
                        text=plan['text'],verification=exc.report,
                        policy=digest(asr_identity)))
            plan.update(status='failed',failed_stage='full_segment',
                        verification=exc.report,rejected_file=str(rejected))
            atomic_json(args.report,plan)
            raise
        check.update(policy=digest(asr_identity),method='faster-whisper-small-full-segment-vad')
        prefix_frames = pcm.sample_rate*args.lead_in_ms//1000
        if pcm.frames[:prefix_frames*2] != b'\0\0'*prefix_frames:
            raise ValueError('Le silence initial n’est pas conforme.')
        atomic_wave(target,pcm)
        write_receipt(target,identity,pcm,profile=profile,segment_id=plan['segment_id'],text=plan['text'],
                      lead_in_ms=args.lead_in_ms,verification=check,voice_sha256=voice_sha,
                      components=[dict(file=s['component'],sha256=s['sha256'],emotion=s['emotion'],
                                       parameters=s['parameters']) for s in plan['spans']])
        plan.update(status='ready',sha256=file_hash(target),verification=check,
                    seconds=round(len(pcm.frames)/2/pcm.sample_rate,3),
                    generation_seconds=round(time.monotonic()-started,2))
        atomic_json(args.report,plan)
        print(json.dumps(dict(output_file=str(target),seconds=plan['seconds'],
                              lead_in_ms=args.lead_in_ms,verified=check['passed']),ensure_ascii=False),flush=True)
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
