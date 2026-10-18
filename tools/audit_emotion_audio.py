"""Vérifier les WAV d'une série en réutilisant les preuves ASR de la génération."""
import argparse
import json
from array import array
from pathlib import Path

from audio.tts_batch import atomic_json, digest, file_hash, read_wave, receipt_matches
from engine.content import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    directory = args.directory.resolve()
    plan = json.loads((directory / 'plan.json').read_text(encoding='utf-8'))
    if file_hash(plan['voice_source']) != plan['voice_sha256']:
        raise ValueError('Le fichier vocal de référence a changé depuis la génération.')
    report = dict(method='generation-transcripts-and-preserved-checks',
                  reference_sha256=plan['voice_sha256'], excerpts=[])
    chunks = []
    for item in plan['excerpts']:
        if item['status'] != 'ready':
            raise ValueError('Extrait manquant : ' + item['id'])
        path = Path(item['output_file'])
        pcm = read_wave(path)
        chunks.append(pcm)
        actual_hash = file_hash(path)
        if actual_hash != item['sha256']:
            raise ValueError('Empreinte différente : ' + item['id'])
        if item.get('decision') == 'accepted' and item.get('reuse_from'):
            origin = ROOT / item['reuse_from']
            old = json.loads((origin.parent.parent / 'verification.json').read_text(encoding='utf-8'))
            proof = next(i for i in old['excerpts'] if i['id'] == item['id'])
            if file_hash(origin) != actual_hash or proof['sha256'] != actual_hash:
                raise ValueError('La prise validée a changé : ' + item['id'])
            speech = proof['speech']
            method = proof.get('method', old['method'])
            seed = None
        elif item.get('composition'):
            composition = item['composition']
            final = json.loads(Path(str(path) + '.json').read_text(encoding='utf-8'))
            origin = Path(composition['tail_source'])
            if file_hash(origin) != composition['tail_source_sha256']:
                raise ValueError('La source de la fin conservée a changé.')
            preserved = read_wave(origin).frames[composition['tail_start_frame']*2:]
            if pcm.frames[composition['final_tail_start_frame']*2:] != preserved:
                raise ValueError('La fin validée n’a pas été conservée exactement.')
            intro_path = Path(composition['intro_file'])
            if file_hash(intro_path) != composition['intro_sha256']:
                raise ValueError('L’introduction du raccord a changé.')
            intro_pcm = read_wave(intro_path)
            if pcm.frames[:len(intro_pcm.frames)] != intro_pcm.frames:
                raise ValueError('Le début du raccord est différent de la prise produite.')
            speech = final['verification']
            method = 'verified-composition-with-preserved-tail'
            seed = None
        else:
            normalized = ' '.join(item['text'].split())
            chunk_id = digest({'profile':item['profile'], 'text':normalized})
            chunk = directory / 'cache' / item['profile'] / 'chunks' / (chunk_id + '.wav')
            if not receipt_matches(chunk, chunk_id) or read_wave(chunk).frames != pcm.frames:
                raise ValueError('Le passage contrôlé ne correspond pas au WAV final : ' + item['id'])
            proof = json.loads(Path(str(chunk) + '.json').read_text(encoding='utf-8'))
            final = json.loads(Path(str(path) + '.json').read_text(encoding='utf-8'))
            speech = proof['verification']
            if (proof['text'] != normalized or not final['verification']['passed'] or
                    final['verification']['policy'] != speech['policy']):
                raise ValueError('Preuve ASR incohérente : ' + item['id'])
            method = 'faster-whisper-local-generation'
            seed = proof['seed']
        if not speech['passed']:
            raise ValueError('Paroles à vérifier : ' + item['id'])
        samples = array('h', pcm.frames)
        peak = max(abs(s) for s in samples) / 32768
        clipped = sum(abs(s) >= 32760 for s in samples) / len(samples)
        report['excerpts'].append(dict(id=item['id'], expected_text=item['text'],
            sha256=actual_hash, hash_matches=True, seconds=len(samples)/pcm.sample_rate,
            peak=round(peak, 4), clipped_fraction=round(clipped, 6), method=method,
            speech=speech, seed=seed, reused_from=item.get('reuse_from')))
    combined = read_wave(directory / 'tous_les_extraits.wav')
    if any(c.sample_rate != combined.sample_rate for c in chunks):
        raise ValueError('Fréquences différentes dans la compilation.')
    if combined.frames != (b'\0\0' * combined.sample_rate).join(c.frames for c in chunks):
        raise ValueError('Compilation différente des extraits individuels.')
    report['combined_seconds'] = len(combined.frames)/2/combined.sample_rate
    atomic_json(directory / 'verification.json', report)
    print(json.dumps(dict(excerpts=len(chunks), speech_checks_passed=len(chunks),
        accepted_preserved=sum(bool(i.get('reuse_from')) for i in plan['excerpts']),
        combined_seconds=report['combined_seconds'],
        clipped_samples=any(i['clipped_fraction'] > 0 for i in report['excerpts'])), ensure_ascii=False))


if __name__ == '__main__':
    main()
