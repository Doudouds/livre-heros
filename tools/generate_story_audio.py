"""Générer un conte balisé, toutes variantes de choix comprises, avec reprise."""
import argparse
import copy
from collections import deque
import os
from pathlib import Path
import shutil
import sys
import wave

from audio.styled_generation import StyledRun
from audio.tts_batch import atomic_json, digest, file_hash
from engine.book_engine import BookEngine
from engine.content import Content, ROOT
from tools.compile_voice_tags import compile_tale
from tools.generate_book_audio import future_flags
from tools.generate_faithful_audio import normalize


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--book',default='roi_grenouille')
    source = result.add_mutually_exclusive_group()
    source.add_argument('--all-segments',action='store_true',help='Tous les textes accessibles (comportement par défaut)')
    source.add_argument('--segment',type=int,help='Un passage sur le parcours --choice')
    result.add_argument('--choice',type=int,choices=(1,2),default=1)
    result.add_argument('--limit',type=int,help='Limiter le nombre de fichiers à traiter, fichiers prêts compris')
    result.add_argument('--voice',type=Path,default=ROOT/'chatterbox/Recording.wav')
    result.add_argument('--output-dir',type=Path)
    result.add_argument('--cache-dir',type=Path)
    result.add_argument('--report',type=Path)
    result.add_argument('--asr-model-dir',type=Path)
    result.add_argument('--chunk-chars',type=int,default=300)
    result.add_argument('--pause-ms',type=int,default=150)
    result.add_argument('--seed',type=int,default=20261018)
    result.add_argument('--threads',type=int,default=8)
    result.add_argument('--attempts',type=int,default=3,help='Essais par prise et par contrôle intégral, bornés à chaque lancement')
    result.add_argument('--dry-run',action='store_true',help='Compiler et exporter le plan sans charger les modèles')
    return result


def plan_current(engine, args, palette):
    scene = engine.current
    authored = engine.scenes[scene['id']]
    if not authored.get('audio_spans'):
        raise ValueError(f"Balisage vocal absent : {scene['id']}")
    spans = copy.deepcopy(authored['audio_spans'])
    if scene['text'] != authored['text']:
        if not scene['text'].endswith(authored['text']):
            raise ValueError('Texte dynamique non balisé.')
        lead = scene['text'][:-len(authored['text'])].strip()
        previous = engine.journal['choices'][-1]
        choices = engine.scenes[previous['scene']]['choices']
        choice = next(c for c in choices if c['id'] == previous['choice_id'])
        if choice['consequence'] != lead or not choice.get('consequence_audio_spans'):
            raise ValueError('Raccord de choix non balisé.')
        spans = copy.deepcopy(choice['consequence_audio_spans'])+spans
    if scene['choice_prompt']:
        for span in copy.deepcopy(authored['choice_audio_spans']):
            span['role'] = 'choix'
            spans.append(span)
    for span in spans:
        span['parameters'] = copy.deepcopy(palette['profiles'][span['emotion']])
    if normalize(' '.join(s['text'] for s in spans)) != normalize(scene['spoken_text']):
        raise ValueError('Les portions vocales ne couvrent pas exactement le texte joué et les choix.')
    return dict(book=args.book,scene_id=scene['id'],segment_id=scene['segment_id'],title=scene['title'],
                text=scene['spoken_text'],spans=spans,
                output_file=str(args.output_dir/(scene['segment_id']+'.wav')),
                lead_in_ms=1000,pause_ms=args.pause_ms,
                palette_sha256=file_hash(ROOT/'audio/emotion_profiles.json'),
                palette_source=palette['approved_take'],chunk_chars=args.chunk_chars,seed=args.seed)


def plans_for_book(args, content=None):
    content = content or Content()
    first = BookEngine(content,args.book)
    if first.book.get('audio_tagged_version') != 1:
        raise ValueError('Compiler le balisage vocal de ce conte avant sa génération.')
    palette = Content.read(ROOT/'audio/emotion_profiles.json')
    if args.segment is not None:
        if not 1 <= args.segment <= len(first.book['scenes']):
            raise ValueError('Numéro de passage hors du conte.')
        for _ in range(args.segment-1):
            first.choose(args.choice-1)
            first.advance()
        return [plan_current(first,args,palette)]
    needed = future_flags(first.book)
    queue,seen,expanded,plans = deque([first]),set(),set(),[]
    while queue:
        engine = queue.popleft()
        if engine.current['segment_id'] not in seen:
            seen.add(engine.current['segment_id'])
            plans.append(plan_current(engine,args,palette))
        key = (engine.current['id'],frozenset(engine.state.flags & needed[engine.current['id']]))
        if engine.finished or key in expanded:
            continue
        expanded.add(key)
        for index in range(len(engine.current['choices'])):
            branch = copy.copy(engine)
            branch.state = copy.deepcopy(engine.state)
            branch.journal = {**engine.journal,'scenes':[],'choices':[]}
            branch.choose(index)
            branch.advance()
            queue.append(branch)
    return plans


def voice_snapshot(voice, cache_dir):
    voice = Path(voice)
    with wave.open(str(voice),'rb') as wav:
        duration = wav.getnframes()/wav.getframerate()
        if wav.getnchannels() not in (1,2) or wav.getcomptype() != 'NONE' or duration < 3:
            raise ValueError('Référence attendue : WAV PCM mono/stéréo contenant au moins trois secondes.')
    sha = file_hash(voice)
    target = Path(cache_dir)/'references'/(sha+'.wav')
    if not target.is_file() or file_hash(target) != sha:
        target.parent.mkdir(parents=True,exist_ok=True)
        temporary = target.with_suffix('.wav.partial')
        shutil.copyfile(voice,temporary)
        if file_hash(temporary) != sha:
            raise ValueError('La référence a changé pendant sa copie ; relancer.')
        os.replace(temporary,target)
    return target,sha


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if not 1 <= args.threads <= 32 or not 1 <= args.attempts <= 10:
            raise ValueError('Threads : 1 à 32 ; tentatives : 1 à 10.')
        if not 80 <= args.chunk_chars <= 1000 or not 0 <= args.pause_ms <= 3000:
            raise ValueError('Découpage : 80 à 1 000 caractères ; pauses : 0 à 3 000 ms.')
        if args.limit is not None and args.limit < 1:
            raise ValueError('--limit doit être positif.')
        compile_tale(args.book)
        content = Content()
        configured = content.config['book_audio_roots'].get(args.book)
        if args.output_dir is None and not configured:
            raise ValueError('Ajouter le dossier audio du conte à config.json avant sa production.')
        args.output_dir = (args.output_dir or ROOT/configured).resolve()
        args.cache_dir = (args.cache_dir or ROOT/'audio/experiments'/args.book/'cache').resolve()
        args.report = (args.report or ROOT/'reports'/args.book/'generation_status.json').resolve()
        plans = plans_for_book(args,content)
        total = len(plans)
        if args.limit:
            plans = plans[:args.limit]
        print(f"{content.books[args.book]['title']} : {total} textes distincts ; {len(plans)} à traiter.",flush=True)
        print(f'Sorties : {args.output_dir}\nÉtat : {args.report}',flush=True)
        if args.dry_run:
            target = args.report.with_name('audio_plan.json')
            atomic_json(target,dict(book=args.book,total=total,segments=plans,dry_run=True))
            print(f'Plan enregistré : {target}. Aucun audio généré.',flush=True)
            return 0
        settings = Content.read(ROOT/'audio/generation_settings.json')
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        os.environ['TOKENIZERS_PARALLELISM'] = 'false'
        dependency_dir = ROOT/settings['asr_dependencies']
        if not dependency_dir.is_dir():
            raise ValueError(f'Dépendances ASR absentes : {dependency_dir}. Voir docs/creation_conte_audio.md.')
        sys.path.insert(0,str(dependency_dir))
        print('Préparation des modèles locaux et contrôle des empreintes…',flush=True)
        import torch
        torch.set_num_threads(args.threads)
        torch.set_num_interop_threads(1)
        from audio.chatterbox_backend import ChatterboxBackend, environment_identity, prepare_model
        from audio.speech_verification import SpeechVerifier, prepare_asr
        args.cache_dir.mkdir(parents=True,exist_ok=True)
        model_lock = args.cache_dir/'model_revision.json'
        if not model_lock.exists():
            atomic_json(model_lock,settings['model'])
        model_dir,model = prepare_model(args.cache_dir)
        environment = environment_identity()
        asr_dir,asr_identity = prepare_asr(args.cache_dir,model_dir=args.asr_model_dir or ROOT/settings['asr_model'])
        reference,voice_sha = voice_snapshot(args.voice,args.cache_dir)
        runner = StyledRun(cache_dir=args.cache_dir,output_dir=args.output_dir,report=args.report,
                           voice_sha=voice_sha,model=model,environment=environment,threads=args.threads,
                           backend_factory=lambda parameters:ChatterboxBackend(model_dir,reference,'cpu',parameters),
                           verifier_factory=lambda:SpeechVerifier(asr_dir),verifier_identity=asr_identity,
                           attempts=args.attempts,progress=lambda message:print(message,flush=True))
        print('Ctrl+C interrompt. Relancer exactement la même commande reprend les prises validées.',flush=True)
        result = runner.run(plans)
        print(f"Terminé : {runner.state['ready']} prêts, {runner.state['failed']} en échec. État : {args.report}",flush=True)
        return result
    except KeyboardInterrupt:
        print('\nInterruption enregistrée. La même commande reprendra sans refaire les prises validées.',file=sys.stderr)
        return 130
    except Exception as exc:
        print(f'Arrêt : {exc}\nLes prises validées restent en cache. Même commande pour reprendre.',file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
