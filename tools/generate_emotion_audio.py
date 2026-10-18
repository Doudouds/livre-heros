"""Dix essais courts Chatterbox V3, avec réglages et référence traçables.

Depuis le projet : .venv-tts/Scripts/python.exe -m tools.generate_emotion_audio
"""
import argparse
import html
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

from audio.tts_batch import (
    Batch, PCM, atomic_json, atomic_wave, batch_lock, digest, file_hash, read_wave,
    receipt_matches, write_receipt,
)
from engine.content import ROOT


# Hypothèses d'interprétation à évaluer à l'écoute, pas des catégories
# émotionnelles natives du modèle. La température reste fixe pour ce premier lot.
PRESETS = {
    '01_joie': (0.80, 0.35),
    '02_tristesse': (0.30, 0.25),
    '03_colere': (0.95, 0.40),
    '04_peur': (0.70, 0.30),
    '05_emerveillement': (0.60, 0.30),
    '06_tendresse': (0.25, 0.30),
    '07_surprise': (0.85, 0.35),
    '08_determination': (0.65, 0.45),
    '09_soulagement': (0.40, 0.30),
    '10_malice': (0.70, 0.35),
}


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--excerpts', type=Path, default=ROOT / 'chatterbox/emotion_excerpts.json')
    result.add_argument('--voice', type=Path, default=ROOT / 'chatterbox/Recording.wav')
    result.add_argument('--take', default='essai_01')
    result.add_argument('--excerpt', action='append')
    result.add_argument('--device', default='auto', choices=('auto', 'cpu', 'cuda'))
    result.add_argument('--threads', type=int, default=8)
    result.add_argument('--seed', type=int, default=20261018)
    result.add_argument('--exaggeration', type=float)
    result.add_argument('--cfg-weight', type=float)
    result.add_argument('--asr-model-dir', type=Path, help='Contrôler les paroles avec un modèle Whisper local')
    result.add_argument('--dry-run', action='store_true')
    return result


def listening_page(directory, plan):
    cards = []
    playlist = ['#EXTM3U']
    for item in plan['excerpts']:
        if item.get('status') != 'ready':
            continue
        name = Path(item['output_file']).name
        escape = html.escape
        parameters = item['parameters']
        cards.append(
            '<article><h2>' + escape(item['emotion']) + '</h2><p>'
            + escape(item['intention']) + '</p><blockquote>' + escape(item['text'])
            + '</blockquote><audio controls preload="none" src="files/' + name
            + '"></audio><p class="settings">Expressivité : '
            + str(parameters['exaggeration']) + ' · CFG : ' + str(parameters['cfg_weight'])
            + ' · ' + str(item['seconds']) + ' s</p></article>'
        )
        playlist.extend(['#EXTINF:' + str(item['seconds']) + ',' + item['emotion'], 'files/' + name])
    page = '''<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Essais émotionnels — Chatterbox V3</title>
<style>body{font:17px/1.5 system-ui;margin:32px auto;max-width:850px;padding:0 20px;background:#f7f5f0;color:#242a32}h1{font-size:30px}h2{font-size:23px}article{background:white;padding:20px 26px;margin:20px 0;border-radius:14px}blockquote{margin:16px 0}audio{width:100%}.settings{font-size:14px;color:#586270}</style>
<h1>Essais émotionnels — Chatterbox V3</h1>
<p>Même référence vocale pour tous les extraits. Les émotions sont les intentions recherchées ; elles restent à évaluer à l'écoute.</p>
<p>Pour chaque extrait : émotion perceptible, ressemblance de la voix, débit, naturel et paroles complètes.</p>'''
    (directory / 'ecouter.html').write_text(page + '\n'.join(cards) + '</html>\n', encoding='utf-8')
    (directory / 'playlist.m3u8').write_text('\n'.join(playlist) + '\n', encoding='utf-8')


def assemble_preserved_tail(item, record, batch, directory, verifier_factory, verifier_identity):
    """Conserver les échantillons de la fin validée, après une nouvelle introduction."""
    tail = item['preserve_tail']
    origin = (ROOT / tail['source']).resolve()
    if file_hash(origin) != tail['sha256']:
        raise ValueError('La prise dont la fin doit être conservée a changé.')
    old = read_wave(origin)
    intro = read_wave(record['target'])
    start = tail['start_frame']
    if (type(start) is not int or not 0 < start < len(old.frames)//2 or
            old.sample_rate != intro.sample_rate or old.sample_rate != tail['sample_rate']):
        raise ValueError('Point de raccord audio invalide.')
    if item['text'] != item['intro_text'] + ' ' + tail['text']:
        raise ValueError('Le texte complet ne correspond pas aux deux parties.')
    gap_frames = intro.sample_rate * tail.get('pause_ms', 80) // 1000
    preserved = old.frames[start*2:]
    pcm = PCM(intro.sample_rate, intro.frames + b'\0\0'*gap_frames + preserved)
    if not verifier_factory:
        raise ValueError('Le raccord nécessite un contrôle des paroles complet.')
    check = verifier_factory().verify(item['text'], pcm)
    check['policy'] = digest(verifier_identity)
    composition = dict(intro_file=str(record['target']), intro_sha256=file_hash(record['target']),
                       intro_text=item['intro_text'], intro_profile=batch.profile,
                       tail_source=str(origin), tail_source_sha256=tail['sha256'],
                       tail_start_frame=start, tail_frames=len(preserved)//2,
                       final_tail_start_frame=len(intro.frames)//2+gap_frames,
                       pause_frames=gap_frames, sample_rate=pcm.sample_rate)
    profile = digest(composition)
    target = Path(item['output_file'])
    identity = digest(dict(profile=profile, text=item['text'], segment_id=item['id']))
    atomic_wave(target, pcm)
    write_receipt(target, identity, pcm, profile=profile, segment_id=item['id'],
                  composition=composition, verification=check)
    atomic_json(directory / 'cache' / profile / 'recipe.json', composition)
    item.update(profile=profile, generation_profile=batch.profile, composition=composition)
    return profile


def main(argv=None):
    args = parser().parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.take):
        raise ValueError('Nom de prise invalide.')
    if not 1 <= args.threads <= 32:
        raise ValueError('Nombre de threads invalide.')
    if args.exaggeration is not None and not 0 <= args.exaggeration <= 2:
        raise ValueError('Expressivité invalide.')
    if args.cfg_weight is not None and not 0 <= args.cfg_weight <= 1:
        raise ValueError('CFG invalide.')
    source = json.loads(args.excerpts.read_text(encoding='utf-8'))
    if args.excerpt and set(args.excerpt) - {e['id'] for e in source['excerpts']}:
        raise ValueError('Identifiant d’extrait absent du document source.')
    excerpts = [e for e in source['excerpts'] if not args.excerpt or e['id'] in args.excerpt]
    if not excerpts or len({e['id'] for e in excerpts}) != len(excerpts):
        raise ValueError('Liste des extraits vide ou identifiants dupliqués.')
    voice_sha = file_hash(args.voice)
    directory = ROOT / 'audio/experiments/emotions' / (args.take + '_' + voice_sha[:12])
    cache = directory / 'cache'
    files = directory / 'files'
    plan = {
        'take': args.take, 'voice_source': str(args.voice.resolve()),
        'voice_sha256': voice_sha, 'source_sha256': file_hash(args.excerpts),
        'seed': args.seed, 'excerpts': [],
        'note': 'Réglages expérimentaux ; aucune commande émotionnelle native ni modification du timbre après synthèse.',
    }
    for excerpt in excerpts:
        exaggeration, cfg = PRESETS.get(excerpt['id'], (0.5, 0.3))
        parameters = dict(
            exaggeration=exaggeration if args.exaggeration is None else args.exaggeration,
            cfg_weight=cfg if args.cfg_weight is None else args.cfg_weight,
            temperature=0.8, repetition_penalty=1.2, min_p=0.05, top_p=1.0,
        )
        overrides = excerpt.get('parameters', {})
        if set(overrides) - set(parameters):
            raise ValueError('Paramètre vocal inconnu dans le document source.')
        parameters.update(overrides)
        if args.exaggeration is not None:
            parameters['exaggeration'] = args.exaggeration
        if args.cfg_weight is not None:
            parameters['cfg_weight'] = args.cfg_weight
        if (not 0 <= parameters['exaggeration'] <= 2 or
                not 0 <= parameters['cfg_weight'] <= 1 or
                not 0 < parameters['temperature'] <= 2):
            raise ValueError('Réglages vocaux hors limites dans le document source.')
        plan['excerpts'].append({**excerpt, 'parameters': parameters,
            'output_file': str(files / (excerpt['id'] + '.wav')), 'status': 'pending'})
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if args.dry_run:
        return 0

    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    import torch
    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(1)
    from audio.chatterbox_backend import ChatterboxBackend, choose_device, environment_identity, prepare_model
    device = choose_device(args.device)
    with batch_lock(directory / '.generation.lock'):
        # Épingler les mêmes poids que les productions existantes, sans requête réseau.
        revision_path = ROOT / 'audio/experiments/passeuse_ch1/cache/model_revision.json'
        revision = json.loads(revision_path.read_text(encoding='utf-8'))
        if revision.get('repo') != 'ResembleAI/chatterbox' or revision.get('variant') != 'v3':
            raise ValueError('Révision de référence incompatible.')
        if not (cache / 'model_revision.json').is_file():
            atomic_json(cache / 'model_revision.json', revision)
        model_dir, model_identity = prepare_model(cache)
        environment = environment_identity()
        reference = cache / 'references' / (voice_sha + '.wav')
        reference.parent.mkdir(parents=True, exist_ok=True)
        if not reference.is_file() or file_hash(reference) != voice_sha:
            temporary = reference.with_suffix('.wav.partial')
            shutil.copyfile(args.voice, temporary)
            if file_hash(temporary) != voice_sha:
                raise ValueError('La référence a changé pendant sa copie.')
            os.replace(temporary, reference)
        plan.update(device=device, threads=args.threads, model=model_identity, environment=environment)
        if args.excerpt and (directory / 'plan.json').is_file():
            previous = json.loads((directory / 'plan.json').read_text(encoding='utf-8'))
            if previous['voice_sha256'] != voice_sha:
                raise ValueError('Référence différente du lot existant.')
            updates = {i['id']: i for i in plan['excerpts']}
            plan['excerpts'] = [updates.get(i['id'], i) for i in previous['excerpts']]
        verifier_factory, verifier_identity = None, None
        if args.asr_model_dir:
            dependencies = ROOT / 'tmp/emotions_asr_deps'
            if dependencies.is_dir():
                sys.path.insert(0, str(dependencies))
            from audio.speech_verification import SpeechVerifier, prepare_asr
            asr_directory, verifier_identity = prepare_asr(cache, model_dir=args.asr_model_dir)
            verifier_factory = lambda: SpeechVerifier(asr_directory)
        atomic_json(directory / 'plan.json', plan)
        backend = None

        def shared_backend():
            nonlocal backend
            if backend is None:
                print('Chargement unique du modèle V3...', flush=True)
                backend = ChatterboxBackend(model_dir, reference, device, plan['excerpts'][0]['parameters'])
            return backend

        selected = [i for i in plan['excerpts'] if not args.excerpt or i['id'] in args.excerpt]
        for index, item in enumerate(selected, 1):
            print(f"\n[{index}/{len(selected)}] {item['emotion']} | {item['parameters']}", flush=True)
            started = time.monotonic()
            parameters = item['parameters']
            recipe = dict(voice_sha256=voice_sha, language='fr', model=model_identity,
                          environment=environment, device=device, parameters=parameters,
                          torch_threads=args.threads)

            def factory():
                synthesizer = shared_backend()
                synthesizer.parameters = parameters
                return synthesizer

            reuse_from = item.get('reuse_from')
            item_verifier = None if reuse_from else verifier_factory
            batch = Batch(cache, recipe, factory, splitter='whole-text-v1',
                          max_chars=380, pause_ms=150, seed=args.seed,
                          attempts=3 if item_verifier else 1,
                          verifier_factory=item_verifier,
                          verifier_identity=verifier_identity if item_verifier else None)
            composed = bool(item.get('preserve_tail'))
            record = dict(segment_id=item['id'] + ('_intro' if composed else ''),
                          scene_id=item['id'], role='dialogue',
                          text=item['intro_text'] if composed else item['text'],
                          target=(directory / 'components' / (item['id'] + '_intro.wav'))
                          if composed else Path(item['output_file']))
            if reuse_from and not record['target'].exists():
                origin = (ROOT / reuse_from).resolve()
                origin_plan = json.loads((origin.parent.parent / 'plan.json').read_text(encoding='utf-8'))
                baseline = next(i for i in origin_plan['excerpts'] if i['id'] == item['id'])
                if (origin_plan['voice_sha256'] != voice_sha or baseline['text'] != item['text'] or
                        not receipt_matches(origin, batch.identity(record))):
                    raise ValueError('La prise validée ne correspond pas au texte, à la voix ou aux réglages.')
                record['target'].parent.mkdir(parents=True, exist_ok=True)
                temporary = record['target'].with_suffix('.wav.partial')
                shutil.copyfile(origin, temporary)
                if file_hash(temporary) != baseline['sha256']:
                    raise ValueError('Copie de la prise validée non conforme.')
                os.replace(temporary, record['target'])
                origin_receipt = json.loads(Path(str(origin) + '.json').read_text(encoding='utf-8'))
                atomic_json(Path(str(record['target']) + '.json'), origin_receipt)
                print('Prise déjà validée par l’utilisateur : copie exacte conservée.', flush=True)
            stats = batch.run([record])
            if stats['failed']:
                item.update(status='failed', generation_seconds=round(time.monotonic() - started, 2))
            else:
                profile = (assemble_preserved_tail(item, record, batch, directory,
                           verifier_factory, verifier_identity) if composed else batch.profile)
                target = Path(item['output_file'])
                pcm = read_wave(target)
                receipt = json.loads(Path(str(target) + '.json').read_text(encoding='utf-8'))
                item.update(status='ready', seconds=round(len(pcm.frames) / 2 / pcm.sample_rate, 3),
                            sha256=file_hash(target), profile=profile,
                            generation_seconds=round(time.monotonic() - started, 2),
                            speech_verification=receipt.get('verification'))
                print(f"Prêt : {item['seconds']} s | calcul {item['generation_seconds']} s", flush=True)
            atomic_json(directory / 'plan.json', plan)
            listening_page(directory, plan)

        ready = [i for i in plan['excerpts'] if i['status'] == 'ready']
        if len(ready) == len(plan['excerpts']):
            chunks = [read_wave(i['output_file']) for i in ready]
            rate = chunks[0].sample_rate
            if any(c.sample_rate != rate for c in chunks):
                raise ValueError('Fréquences différentes entre les extraits.')
            # Ordre du plan ; une seconde de silence entre les extraits, sans annonce parlée.
            joined = (b'\0\0' * rate).join(c.frames for c in chunks)
            atomic_wave(directory / 'tous_les_extraits.wav', PCM(rate, joined))
        print(f"\n{len(ready)}/{len(plan['excerpts'])} extraits prêts : {directory}", flush=True)
        return 0 if len(ready) == len(plan['excerpts']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
