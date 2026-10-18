"""Contrôle local des dix essais : format, empreinte et paroles, sans prompt ASR."""
import argparse
import json
import math
import sys
import time
from array import array
from pathlib import Path

from audio.speech_verification import IncompleteSpeech, compare_transcript
from audio.tts_batch import atomic_json, file_hash, read_wave
from engine.content import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--model-dir', type=Path)
    args = parser.parse_args()
    if args.model_dir is None:
        snapshots = ROOT / 'audio/experiments/emotions/asr_cache/models--Systran--faster-whisper-base/snapshots'
        candidates = [p for p in snapshots.glob('*') if (p / 'model.bin').is_file()]
        if len(candidates) != 1:
            raise ValueError('Indiquer --model-dir pour choisir le modèle ASR local.')
        args.model_dir = candidates[0]
    isolated_dependencies = ROOT / 'tmp/emotions_asr_deps'
    if isolated_dependencies.is_dir():
        sys.path.insert(0, str(isolated_dependencies))
    from faster_whisper import WhisperModel
    model = WhisperModel(str(args.model_dir), device='cpu', compute_type='int8',
                         cpu_threads=4, num_workers=1, local_files_only=True)
    plan = json.loads((args.directory / 'plan.json').read_text(encoding='utf-8'))
    model_directory = args.model_dir.resolve()
    method = model_directory.parent.parent.name.removeprefix('models--Systran--')
    if not method.startswith('faster-whisper-'):
        method = 'faster-whisper-local'
    report = dict(method=method, model_directory=str(model_directory),
                  reference_sha256=plan['voice_sha256'], excerpts=[])
    previous = {}
    if (args.directory / 'verification.json').is_file():
        old_report = json.loads((args.directory / 'verification.json').read_text(encoding='utf-8'))
        if (old_report.get('method') == report['method'] and
                old_report.get('model_directory') == report['model_directory'] and
                old_report.get('reference_sha256') == report['reference_sha256']):
            previous = {r['id']: r for r in old_report['excerpts']}
    for item in plan['excerpts']:
        if item['status'] != 'ready':
            continue
        started = time.monotonic()
        path = Path(item['output_file'])
        current_hash = file_hash(path)
        if item.get('reuse_from') and item.get('decision') == 'accepted':
            origin = ROOT / item['reuse_from']
            origin_report = json.loads((origin.parent.parent / 'verification.json').read_text(encoding='utf-8'))
            checked = next(i for i in origin_report['excerpts'] if i['id'] == item['id'])
            if (checked['sha256'] != current_hash or checked['expected_text'] != item['text'] or
                    not checked['speech']['passed']):
                raise ValueError('La preuve des paroles de la prise conservée ne correspond pas au fichier.')
            report['excerpts'].append({**checked, 'hash_matches':current_hash == item['sha256'],
                                       'reused_from':str(origin), 'method':origin_report['method'],
                                       'model_directory':origin_report['model_directory']})
            print(item['id'] + ' : prise validée et contrôle antérieur conservés.', flush=True)
            continue
        old = previous.get(item['id'])
        if old and old.get('sha256') == current_hash and old.get('expected_text') == item['text']:
            report['excerpts'].append(old)
            print(item['id'] + ' : contrôle conservé, fichier identique.', flush=True)
            continue
        pcm = read_wave(path)
        samples = array('h', pcm.frames)
        peak = max(abs(s) for s in samples) / 32768
        rms = math.sqrt(sum(float(s) * s for s in samples) / len(samples)) / 32768
        segments, _ = model.transcribe(str(path), language='fr', beam_size=5,
                                      temperature=0, condition_on_previous_text=False,
                                      vad_filter=False)
        transcript = ' '.join(s.text.strip() for s in segments)
        try:
            speech = compare_transcript(item['text'], transcript)
        except IncompleteSpeech as exc:
            speech = exc.report
        result = dict(id=item['id'], sha256=current_hash, expected_text=item['text'],
                      method=method, model_directory=str(model_directory),
                      hash_matches=current_hash == item['sha256'],
                      seconds=len(samples) / pcm.sample_rate,
                      peak=round(peak, 4), rms=round(rms, 4),
                      clipped_fraction=round(sum(abs(s) >= 32760 for s in samples) / len(samples), 6),
                      speech=speech, check_seconds=round(time.monotonic() - started, 2))
        report['excerpts'].append(result)
        atomic_json(args.directory / 'verification.json', report)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    atomic_json(args.directory / 'verification.json', report)
    passed = sum(r['speech']['passed'] and r['hash_matches'] for r in report['excerpts'])
    print(f'{passed}/{len(plan["excerpts"])} extraits conformes au contrôle automatique.', flush=True)
    return 0 if passed == len(plan['excerpts']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
