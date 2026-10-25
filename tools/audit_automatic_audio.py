"""Audit des WAV automatiques : texte joué, profils, échantillons et jugement final indépendant."""
import argparse
import json
from pathlib import Path

from audio.tts_batch import atomic_json, digest, file_hash, read_wave, receipt_matches, receipt_path
from audio.verification_evidence import validate_evidence
from engine.content import Content, ROOT
from tools.generate_faithful_audio import assemble
from tools.generate_story_audio import parser as generation_parser, plans_for_book


def audit(book_id):
    content = Content()
    folder = ROOT/'reports'/book_id/'automatic'
    state = Content.read(folder/'generation_status.json')
    output = (ROOT/content.config['book_audio_roots'][book_id]).resolve()
    args = generation_parser().parse_args(['--book',book_id,'--automatic'])
    args.output_dir = output
    plans = plans_for_book(args,content)
    voice_sha = file_hash(ROOT/'chatterbox/Recording.wav')
    palette_sha = file_hash(ROOT/'audio/emotion_profiles.json')
    assert state['voice_sha256'] == voice_sha,'Référence vocale modifiée.'
    results = []
    for plan in plans:
        try:
            target = Path(plan['output_file'])
            proof = Content.read(receipt_path(target))
            assert receipt_matches(target,proof['identity']),'WAV ou reçu corrompu.'
            assert proof['text'] == plan['text'] and proof['segment_id'] == plan['segment_id'],'Texte joué différent.'
            assert proof['voice_sha256'] == voice_sha,'Mélange de voix.'
            assert proof['verification']['policy'] == state['policy'],'Politique de contrôle différente.'
            assert proof['verification'].get('final_review_required') is True,'Arbitrage final absent.'
            assert proof['verification'].get('review_verifier') == 'Whisper Medium','Vérificateur final différent.'
            assert len(proof['components']) == len(plan['spans']),'Portions manquantes.'
            parts,recipes = [],[]
            for span,component in zip(plan['spans'],proof['components']):
                path = Path(component['file'])
                recipe = Content.read(path.parent.parent/'recipe.json')
                assert digest(recipe) == path.parent.parent.name,'Profil du cache corrompu.'
                assert recipe['parameters'] == component['parameters'] == span['parameters'],'Ton modifié.'
                assert component['emotion'] == span['emotion'],'Émotion différente du balisage.'
                assert recipe['voice_sha256'] == voice_sha and recipe['palette_sha256'] == palette_sha,'Référence ou palette différente.'
                assert file_hash(path) == component['sha256'],'Prise corrompue.'
                component_proof = Content.read(receipt_path(path))
                assert component_proof['verification']['passed'] is True,'Prise non vérifiée.'
                recipes.append(recipe)
                parts.append(read_wave(path))
            base = recipes[0]
            assert all(r['model'] == base['model'] and r['environment'] == base['environment'] for r in recipes),'Mélange de modèles TTS.'
            profile = digest(dict(plan=plan,voice=voice_sha,model=base['model'],environment=base['environment'],
                                  threads=base['torch_threads'],pipeline='faithful-styled-v1'))
            identity = digest(dict(profile=profile,text=plan['text'],segment_id=plan['segment_id']))
            assert proof['profile'] == profile and receipt_matches(target,identity),'Identité texte/voix incohérente.'
            pcm = read_wave(target)
            assert pcm == assemble(parts,1000,plan['pause_ms']),'Assemblage différent des prises.'
            assert content.books[book_id]['audio_lead_in_ms'] == 0,'Silence ajouté par le lecteur.'
            validate_evidence(plan['text'],proof['verification'],pcm,
                              tail_text=plan['spans'][-1]['text'],tail_pcm=parts[-1])
            results.append(dict(segment_id=plan['segment_id'],passed=True,
                                sha256=file_hash(target),seconds=len(pcm.frames)/2/pcm.sample_rate,
                                word_error_rate=proof['verification']['word_error_rate']))
        except (OSError,ValueError,AssertionError,KeyError) as exc:
            results.append(dict(segment_id=plan['segment_id'],passed=False,error=str(exc)))
    result = dict(book=book_id,passed=all(r['passed'] for r in results),
                  required=len(plans),ready=sum(r['passed'] for r in results),
                  voice_sha256=voice_sha,palette_sha256=palette_sha,segments=results)
    original = folder/'before_medium_wavs.json'
    if original.exists():
        previous = Content.read(original)
        result['previous_wavs_unchanged'] = {name:(output/name).is_file() and file_hash(output/name) == sha
                                              for name,sha in previous.items()}
    atomic_json(folder/'quality_audit_medium.json',result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--book',default='roi_grenouille')
    args = parser.parse_args(argv)
    result = audit(args.book)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
