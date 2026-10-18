"""Chatterbox Multilingual V3 : production locale avec reprise automatique."""
import argparse
import json
import os
import sys
from pathlib import Path

from audio.tts_batch import Batch, atomic_json, batch_lock, file_hash, read_manifest, split_linguistic, split_text
from engine.content import ROOT


def generation_parser(*, include_comparison=True):
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--voice', type=Path, help='Échantillon WAV de ta voix, en français')
    result.add_argument('--device', choices=('auto','cpu','cuda','mps'), default='auto')
    result.add_argument('--cache-dir', type=Path, default=ROOT / 'audio/build_cache')
    result.add_argument('--output-dir', type=Path, help='Autre dossier de sortie pour tester une nouvelle voix')
    result.add_argument('--model-dir', type=Path, help='Poids V3 déjà présents localement')
    result.add_argument('--model-revision', help='Révision Hugging Face ; figée automatiquement au premier lancement')
    result.add_argument('--chunk-chars', type=int, default=380)
    result.add_argument('--pause-ms', type=int, default=160)
    result.add_argument('--seed', type=int, default=20261003)
    result.add_argument('--exaggeration', type=float, default=0.5)
    result.add_argument('--cfg-weight', type=float, default=0.5)
    result.add_argument('--temperature', type=float, default=0.8)
    result.add_argument('--asr-model',choices=('small','medium','large-v3'),default='small',help='Reconnaissance française qui contrôle les paroles')
    result.add_argument('--asr-model-dir',type=Path,help='Modèle faster-whisper déjà préparé hors ligne')
    result.add_argument('--attempts',type=int,default=3,help='Tentatives automatiques par passage suspect, entre 1 et 10')
    result.add_argument('--skip-verification', action='store_true', help='Essai sans Whisper ; les paroles devront être contrôlées à l’écoute')
    result.add_argument('--linguistic', action='store_true', help='Privilégier phrases, puis ;/: et espaces sur un seul texte logique')
    if include_comparison:
        result.add_argument('--compare-single-take', action='store_true', help='Produire aussi une prise longue témoin avec la même voix, sans Whisper')
    else:
        result.set_defaults(compare_single_take=False)
    result.add_argument('--plan-output', type=Path, help='Enregistrer le texte et le découpage dans un plan JSON lisible')
    result.add_argument('--dry-run', action='store_true', help='Chiffrer le travail sans dépendances TTS ni téléchargement')
    result.add_argument('--overwrite', action='store_true', help='Autoriser explicitement une nouvelle voix ou reconstruire un WAV sans reçu')
    return result


def parser():
    result = generation_parser()
    result.add_argument('--manifest', type=Path, default=ROOT / 'reports/tts_manifest.jsonl')
    result.add_argument('--scene', action='append', help='Limiter à un ID de scène ; option répétable')
    result.add_argument('--limit', type=int, help='Premier petit lot, par exemple 6 segments')
    return result


def main(argv=None, *, args=None, records=None):
    args = args if args is not None else parser().parse_args(argv)
    try:
        if args.limit is not None and args.limit < 1:
            raise ValueError('--limit doit être positif.')
        if not 0 <= args.exaggeration <= 2 or not 0 <= args.cfg_weight <= 1 or not 0 < args.temperature <= 2:
            raise ValueError('Réglages vocaux hors des bornes autorisées.')
        if not 0 <= args.pause_ms <= 3000:
            raise ValueError('Pause invalide.')
        if not 1 <= args.attempts <= 10:
            raise ValueError('Prévoir entre 1 et 10 tentatives.')
        if records is None:
            records = read_manifest(args.manifest, ROOT, args.output_dir)
        if args.scene:
            records = [r for r in records if r['scene_id'] in args.scene]
        if args.limit:
            records = records[:args.limit]
        if not records:
            raise ValueError('Aucun segment ne correspond à la sélection.')
        splitter = split_linguistic if args.linguistic else split_text
        chunks = [splitter(r['text'], args.chunk_chars) for r in records]
        unique = {c for group in chunks for c in group}
        seconds = sum(r.get('estimated_seconds', 0) for r in records) + sum(max(0,len(c)-1)*args.pause_ms/1000 for c in chunks)
        print(json.dumps({'segments': len(records), 'passages_total': sum(map(len,chunks)),
                          'passages_distincts': len(unique), 'heures_audio_estimees': round(seconds/3600,2),
                          'wav_pcm24k_gio_estimes': round(seconds*24000*2/1024**3,2),
                          'texte_des_choix_inclus': True}, ensure_ascii=False, indent=2))
        if args.plan_output:
            atomic_json(args.plan_output, dict(max_chars=args.chunk_chars, pause_ms=args.pause_ms,
                        whisper=not args.skip_verification, compare_single_take=args.compare_single_take,
                        segments=[dict(segment_id=r['segment_id'], scene_id=r['scene_id'],
                                       scene_number=r.get('scene_number'), title=r.get('title'),
                                       variant_number=r.get('variant_number'), output_file=str(r['target']),
                                       text=r['text'], characters=len(r['text']),
                                       chunks=[dict(number=i, characters=len(c), text=c) for i,c in enumerate(group,1)])
                                  for r,group in zip(records,chunks)]))
            print(f'Plan de découpage : {args.plan_output}')
        if args.dry_run:
            return 0
        if args.voice is None or not args.voice.is_file():
            raise ValueError('Indiquer --voice avec un échantillon existant de ta voix ; voir docs/chatterbox_v3.md.')
        # Dépendances lourdes seulement après validation de l'entrée, jamais dans le jeu.
        from audio.chatterbox_backend import ChatterboxBackend, choose_device, environment_identity, prepare_model
        environment = environment_identity()
        device = choose_device(args.device)
        directory, model = prepare_model(args.cache_dir, args.model_dir, args.model_revision)
        verifier_factory, verifier_identity = None, None
        if not args.skip_verification:
            from audio.speech_verification import SpeechVerifier, prepare_asr
            asr_directory, verifier_identity = prepare_asr(args.cache_dir,args.asr_model,args.asr_model_dir)
            verifier_factory = lambda: SpeechVerifier(asr_directory)
        parameters = {'exaggeration':args.exaggeration, 'cfg_weight':args.cfg_weight,
                      'temperature':args.temperature, 'repetition_penalty':1.2, 'min_p':0.05, 'top_p':1.0}
        voice_sha = file_hash(args.voice)
        reference = args.cache_dir / 'references' / (voice_sha + '.wav')
        with batch_lock(args.cache_dir / '.reference.lock'):
            if not reference.is_file() or file_hash(reference) != voice_sha:
                reference.parent.mkdir(parents=True, exist_ok=True)
                temporary = Path(str(reference) + '.partial')
                with args.voice.open('rb') as source, temporary.open('wb') as destination:
                    for block in iter(lambda: source.read(1024*1024), b''):
                        destination.write(block)
                    destination.flush()
                    os.fsync(destination.fileno())
                if file_hash(temporary) != voice_sha:
                    raise ValueError('L’échantillon a changé pendant sa copie ; relancer avec un fichier stable.')
                os.replace(temporary, reference)
        recipe = {'voice_sha256':voice_sha, 'language':'fr', 'model':model,
                  'environment':environment, 'device':device, 'parameters':parameters}
        batch = Batch(args.cache_dir, recipe,
                      lambda: ChatterboxBackend(directory, reference, device, parameters),
                      max_chars=args.chunk_chars, pause_ms=args.pause_ms, seed=args.seed,
                      overwrite=args.overwrite, attempts=args.attempts,
                      verifier_factory=verifier_factory,verifier_identity=verifier_identity,
                      splitter='linguistic-v1' if args.linguistic else 'paragraph-sentence-v1')
        print(f'Voix {recipe["voice_sha256"][:12]} ; Multilingual V3 ; {device}. Reprise automatique activée.')
        print('Contrôle français des paroles activé : texte complet, derniers mots et annonces des choix.'
              if verifier_factory else 'Essai sans Whisper : WAV produits, paroles à vérifier à l’écoute.')
        stats = batch.run(records)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        if args.compare_single_take and not stats['failed']:
            print('Prise longue témoin : même texte, voix et réglages, un seul appel TTS ; sans Whisper.')
            comparison_records = [{**r, 'target': r['target'].with_name(r['target'].stem + '_single_take.wav')} for r in records]
            comparison = Batch(args.cache_dir, recipe, batch.backend, max_chars=args.chunk_chars,
                               pause_ms=args.pause_ms, seed=args.seed, overwrite=args.overwrite,
                               attempts=args.attempts, splitter='whole-text-v1')
            comparison_stats = comparison.run(comparison_records)
            print(json.dumps({'single_take': comparison_stats}, ensure_ascii=False, indent=2))
            stats['failed'] += comparison_stats['failed']
        return 1 if stats['failed'] else 0
    except KeyboardInterrupt:
        print('\nArrêt demandé. Relancer la même commande : les fichiers et passages validés seront conservés.', file=sys.stderr)
        return 130
    except Exception as exc:
        print(f'Arrêt : {exc}\nLes productions déjà validées restent conservées.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
