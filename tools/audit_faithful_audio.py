"""Contrôler les preuves, le texte joué et les échantillons du premier segment."""
import argparse
import json
from pathlib import Path

from audio.speech_verification import compare_transcript
from audio.tts_batch import (SPLITTERS, atomic_json, digest, file_hash,
                            read_wave, receipt_matches, receipt_path)
from engine.book_engine import BookEngine
from engine.content import Content, ROOT
from tools.generate_faithful_audio import assemble, normalize


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def audit(report_path):
    plan = read(report_path)
    if plan.get('status') != 'ready':
        raise ValueError('La génération complète doit être terminée avant l’audit.')
    content = Content()
    engine = BookEngine(content, plan['book'])
    if plan['scene_id'] != engine.current['id']:
        raise ValueError('Cet audit porte sur le premier segment uniquement.')
    assert plan['segment_id'] == engine.current['segment_id']
    assert plan['text'] == engine.current['spoken_text']
    assert normalize(' '.join(s['text'] for s in plan['spans'])) == normalize(plan['text'])
    assert plan['voice_sha256'] == file_hash(ROOT/'chatterbox/Recording.wav')
    palette_path = ROOT/'audio/emotion_profiles.json'
    assert plan['palette_sha256'] == file_hash(palette_path)
    palette = read(palette_path)
    target = Path(plan['output_file'])
    configured_root = ROOT/content.config['book_audio_roots'][plan['book']]
    assert target.parent.resolve() == configured_root.resolve()
    receipt = read(receipt_path(target))
    assert receipt_matches(target, receipt['identity'])
    assert receipt['sha256'] == plan['sha256']
    assert receipt['text'] == plan['text']
    assert receipt['verification'] == plan['verification']
    assert receipt['voice_sha256'] == plan['voice_sha256']
    assert receipt['verification']['passed'] is True
    compare_transcript(plan['text'], receipt['verification']['transcript'])
    checks = []

    def chunk(profile_dir, text):
        key = digest(dict(profile=profile_dir.name, text=text))
        path = profile_dir/'chunks'/(key+'.wav')
        proof = read(receipt_path(path))
        assert receipt_matches(path, key)
        assert proof['text'] == text
        check = proof['verification']
        assert check['passed'] is True
        assert check['policy'] == plan['verification_policy']
        pcm = read_wave(path)
        if check.get('method') == 'verified-parts':
            texts = [read(profile_dir/'chunks'/(key+'.wav.json'))['text'] for key in check['parts']]
            assert normalize(' '.join(texts)) == normalize(text)
            children = [chunk(profile_dir, part) for part in texts]
            assert assemble(children, 0, plan['pause_ms']) == pcm
        else:
            compare_transcript(text, check['transcript'])
            checks.append(dict(file=str(path), sha256=proof['sha256'],
                               word_error_rate=check['word_error_rate']))
        return pcm

    components = []
    for span, recorded in zip(plan['spans'], receipt['components'], strict=True):
        path = Path(span['component'])
        profile_dir = path.parent.parent
        recipe = read(profile_dir/'recipe.json')
        assert digest(recipe) == span['profile'] == profile_dir.name
        assert span['parameters'] == recipe['parameters'] == palette['profiles'][span['emotion']]
        assert recipe['voice_sha256'] == plan['voice_sha256']
        assert recipe['palette_sha256'] == plan['palette_sha256']
        assert file_hash(path) == span['sha256'] == recorded['sha256']
        component = read_wave(path)
        pieces = [chunk(profile_dir, text) for text in SPLITTERS[recipe['splitter']](span['text'], recipe['max_chars'])]
        assert assemble(pieces, 0, recipe['pause_ms']) == component
        components.append(component)
    pcm = read_wave(target)
    assert pcm == assemble(components, 1000, plan['pause_ms'])
    assert plan['lead_in_ms'] == receipt['lead_in_ms'] == 1000
    assert pcm.frames[:pcm.sample_rate*2] == b'\0'*(pcm.sample_rate*2)
    assert engine.book['audio_lead_in_ms'] == 0
    assert engine.book['embedded_lead_in_ms'] == 1000
    final_files = list(target.parent.glob('*.wav'))
    assert target in final_files
    result = dict(passed=True, output_file=str(target), sha256=file_hash(target),
                  segment_id=plan['segment_id'], seconds=len(pcm.frames)/2/pcm.sample_rate,
                  sample_rate=pcm.sample_rate, voice_sha256=plan['voice_sha256'],
                  palette_sha256=plan['palette_sha256'], leading_zero_frames=pcm.sample_rate,
                  playback_extra_lead_in_ms=0, final_wav_count=len(final_files),
                  audited_final_wav_count=1,
                  exact_reassembly=True, runtime_text_matched=True,
                  player_audio_root_matched=True,
                  choices_matched=receipt['verification']['choices_matched'],
                  final_word_error_rate=receipt['verification']['word_error_rate'],
                  verified_chunks=checks)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=ROOT/'reports/roi_grenouille/audio_premier_segment.json')
    args = parser.parse_args()
    result = audit(args.report)
    target = args.report.with_name('audio_audit.json')
    atomic_json(target, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
