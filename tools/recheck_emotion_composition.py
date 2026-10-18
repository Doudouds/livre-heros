"""Évaluer une introduction isolée dans le contexte du raccord complet.

Les contrôles isolés restent enregistrés, y compris leurs refus. Seul un raccord
qui passe le contrôle ASR complet peut devenir le WAV proposé à l'écoute.
"""
import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from audio.tts_batch import PCM, atomic_json, atomic_wave, digest, file_hash, read_wave, write_receipt
from engine.content import ROOT
from tools.generate_emotion_audio import assemble_preserved_tail, listening_page


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--asr-model-dir', type=Path, required=True)
    args = parser.parse_args()
    directory = args.directory.resolve()
    plan = json.loads((directory / 'plan.json').read_text(encoding='utf-8'))
    item = next(i for i in plan['excerpts'] if i.get('preserve_tail'))
    sys.path.insert(0, str(ROOT / 'tmp/emotions_asr_deps'))
    from audio.speech_verification import IncompleteSpeech, SpeechVerifier, prepare_asr
    model_dir, identity = prepare_asr(directory / 'cache', model_dir=args.asr_model_dir)
    verifier = SpeechVerifier(model_dir)
    candidates = []
    for report_path in (directory / 'cache').glob('*/rejected/*/attempt_*.json'):
        proof = json.loads(report_path.read_text(encoding='utf-8'))
        check = proof.get('verification', {})
        if (proof.get('text') == item['intro_text'] and
                check.get('word_error_rate', 1) <= 0.15 and
                check.get('reasons') == ['fin du texte non retrouvée']):
            candidates.append((check['word_error_rate'], -int(proof['attempt']), report_path, proof))
    candidates.sort(key=lambda c: (c[0], c[1]))
    if not candidates:
        raise ValueError('Aucune introduction assez proche du texte pour ce contrôle contextuel.')
    started = time.monotonic()
    target = directory / 'components' / (item['id'] + '_intro.wav')
    for _, _, report_path, proof in candidates:
        candidate = report_path.with_suffix('.wav')
        profile = report_path.parent.parent.parent.name
        pcm = read_wave(candidate)
        atomic_wave(target, pcm)
        chunk_identity = digest(dict(profile=profile, text=item['intro_text'], segment_id=item['id']+'_intro'))
        write_receipt(target, chunk_identity, pcm, profile=profile, text=item['intro_text'],
                      verification=proof['verification'], source_candidate=str(candidate),
                      verification_scope='isolated-introduction; final composition checked separately')
        record = dict(target=target, text=item['intro_text'])
        try:
            final_profile = assemble_preserved_tail(item, record, SimpleNamespace(profile=profile),
                                                     directory, lambda: verifier, identity)
        except IncompleteSpeech as exc:
            print(json.dumps(dict(candidate=str(candidate), full_check=exc.report), ensure_ascii=False), flush=True)
            continue
        final_path = Path(item['output_file'])
        full = read_wave(final_path)
        final_receipt = json.loads(Path(str(final_path) + '.json').read_text(encoding='utf-8'))
        item.update(status='ready', profile=final_profile, sha256=file_hash(final_path),
                    seconds=round(len(full.frames)/2/full.sample_rate, 3),
                    speech_verification=final_receipt['verification'],
                    composition_check_seconds=round(time.monotonic()-started, 2),
                    intro_selection=dict(candidate=str(candidate),
                        isolated_check=proof['verification'],
                        selection_scope='full-composition-verification'))
        atomic_json(directory / 'plan.json', plan)
        chunks = [read_wave(i['output_file']) for i in plan['excerpts'] if i['status'] == 'ready']
        if len(chunks) != len(plan['excerpts']):
            raise ValueError('D’autres extraits restent incomplets.')
        rate = chunks[0].sample_rate
        if any(c.sample_rate != rate for c in chunks):
            raise ValueError('Fréquences différentes dans la compilation.')
        atomic_wave(directory / 'tous_les_extraits.wav', PCM(rate, (b'\0\0'*rate).join(c.frames for c in chunks)))
        listening_page(directory, plan)
        print(json.dumps(dict(selected_candidate=str(candidate), seconds=item['seconds'],
                              full_check=final_receipt['verification']), ensure_ascii=False), flush=True)
        return 0
    raise ValueError('Aucun raccord ne passe le contrôle des paroles complet.')


if __name__ == '__main__':
    raise SystemExit(main())
