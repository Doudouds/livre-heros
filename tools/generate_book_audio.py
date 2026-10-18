"""Chatterbox V3 sur la Passeuse : un segment ou toutes les variantes du chapitre 1.

Lancer depuis le projet : .venv-tts/Scripts/python.exe -m tools.generate_book_audio
"""
import copy
import sys
from collections import deque

from engine.book_engine import BookEngine
from engine.content import Content, ROOT, segment_id
from tools.generate_audio import generation_parser, main as generate

# Réglages du premier essai. Les options CLI permettent de les remplacer.
MAX_CHARS = 300
PAUSE_MS = 150
VOICE = ROOT / 'chatterbox/Recording.wav'
CFG_WEIGHT = 0.30
EXAGGERATION = 0.40


def parser():
    result = generation_parser(include_comparison=False)
    result.description = __doc__
    result.set_defaults(chunk_chars=MAX_CHARS, pause_ms=PAUSE_MS, voice=VOICE,
                        cfg_weight=CFG_WEIGHT, exaggeration=EXAGGERATION,
                        linguistic=True, skip_verification=True, device='cpu',
                        scene=None, limit=None,
                        cache_dir=ROOT / 'audio/experiments/passeuse_ch1/cache',
                        output_dir=ROOT / 'audio/experiments/passeuse_ch1/files')
    source = result.add_mutually_exclusive_group()
    source.add_argument('--segment', type=int, default=1, help='Numéro du segment à tester, 1 par défaut')
    source.add_argument('--chapter', action='store_true', help='Assembler le chapitre 1 sur un parcours choisi en un seul WAV')
    source.add_argument('--all-segments', action='store_true', help='Produire tous les segments accessibles du chapitre 1, toutes variantes de choix incluses')
    result.add_argument('--limit', type=int, help='Limiter à quelques WAV pour un petit lot ; les WAV déjà prêts sont comptés et conservés')
    result.add_argument('--choice', type=int, choices=(1, 2), default=1,
                        help='Choix à chaque décision précédente ; 1 par défaut, pour un parcours reproductible')
    result.add_argument('--verify', dest='skip_verification', action='store_false',
                        help='Activer Whisper et les régénérations des blocs suspects')
    return result


def scene_record(args, content, scene, *, number, variant_number=1):
    key = scene['segment_id']
    target = args.output_dir.resolve() / (key + '.wav')
    return dict(segment_id=key, scene_id=scene['id'], role='narration', text=scene['spoken_text'],
                target=target, output_file=str(target), estimated_seconds=content.seconds(scene['spoken_text']),
                scene_number=number, title=scene.get('title', scene['id']), variant_number=variant_number)


def future_flags(book):
    """Flags lus à partir de chaque scène : fusionner seulement les passés équivalents."""
    result, needed = {}, set()
    for scene in reversed(book['scenes']):
        conditions = [v.get('when', {}) for v in scene.get('variants', [])]
        choices = list(scene.get('choices', []))
        for variant in scene.get('variants', []):
            choices.extend(variant.get('choices', []))
        conditions.extend(v.get('when', {}) for c in choices for v in c.get('consequence_variants', []))
        for condition in conditions:
            for name in ('all', 'none', 'any'):
                needed.update(condition.get(name, []))
        needed.update(e['flag'] for e in scene.get('echoes', []))
        result[scene['id']] = frozenset(needed)
    return result


def all_book_records(args, content=None):
    """Explorer les choix avec le vrai moteur, sans énumérer 2**27 parties.

    Le texte courant est exporté avant fusion : deux conséquences différentes
    restent deux WAV. Le futur dépend uniquement de la scène et des flags encore
    lus ; un passé sans effet futur n'est donc exploré qu'une fois.
    """
    content = content or Content()
    first = BookEngine(content, 'passeuse_ch1')
    relevant = future_flags(first.book)
    numbers = {s['id']: i for i,s in enumerate(first.book['scenes'], 1)}
    queue, expanded, seen, counts, records = deque([first]), set(), set(), {}, []
    while queue:
        engine = queue.popleft()
        scene = engine.current
        if scene['segment_id'] not in seen:
            seen.add(scene['segment_id'])
            counts[scene['id']] = counts.get(scene['id'], 0) + 1
            records.append(scene_record(args, content, scene, number=numbers[scene['id']],
                                        variant_number=counts[scene['id']]))
        state_key = (scene['id'], frozenset(engine.state.flags & relevant[scene['id']]))
        if engine.finished or state_key in expanded:
            continue
        expanded.add(state_key)
        for choice in range(len(scene['choices'])):
            branch = copy.copy(engine)
            branch.state = copy.deepcopy(engine.state)
            # Les journaux historiques ne modifient pas les textes et ne doivent
            # pas être partagés entre les branches.
            branch.journal = {**engine.journal, 'scenes': [], 'choices': []}
            branch.choose(choice)
            branch.advance()
            queue.append(branch)
    return records


def book_record(args, content=None):
    content = content or Content()
    engine = BookEngine(content, 'passeuse_ch1')
    if not args.chapter and not 1 <= args.segment <= len(engine.book['scenes']):
        raise ValueError(f'--segment doit être compris entre 1 et {len(engine.book["scenes"])}.')
    parts = []
    number = 1
    while True:
        scene = engine.current
        parts.append(scene['spoken_text'])
        if engine.finished or (not args.chapter and number == args.segment):
            break
        engine.choose(args.choice - 1)
        engine.advance()
        number += 1
    text = '\n\n'.join(parts) if args.chapter else scene['spoken_text']
    scene_id = 'passeuse_ch1_chapter' if args.chapter else scene['id']
    key = segment_id(scene_id, 'narration', text)
    target = args.output_dir.resolve() / (key + '.wav')
    return dict(segment_id=key, scene_id=scene_id, role='narration', text=text,
                target=target, output_file=str(target), estimated_seconds=content.seconds(text))


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        records = all_book_records(args) if args.all_segments else [book_record(args)]
        label = 'chapitre_1_tous_segments' if args.all_segments else 'chapitre_1' if args.chapter else f'segment_{args.segment:02d}'
        args.plan_output = args.plan_output or ROOT / f'reports/passeuse_audio/{label}_plan.json'
        print(f'La petite passeuse d’étoile | {label}')
        print(f'Voix : {args.voice} | MAX_CHARS = {args.chunk_chars} | PAUSE_MS = {args.pause_ms}')
        if args.all_segments:
            print(f'{len(records)} textes distincts couvrant les {len({r["scene_id"] for r in records})} scènes du chapitre 1.')
            print(f'Dossier des WAV : {args.output_dir}')
            print('Les WAV et blocs déjà intègres seront conservés. Ctrl+C interrompt ; la même commande reprend.')
        else:
            print(f'Choix du parcours : {args.choice} | WAV final : {records[0]["target"]}')
        return generate(args=args, records=records)
    except Exception as exc:
        print(f'Arrêt : {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
