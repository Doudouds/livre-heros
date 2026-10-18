"""Chatterbox V3 : tous les textes accessibles de La Maison aux Sept Cages."""
import copy
import itertools
import json
import random
import sys
from collections import deque

from audio.tts_batch import atomic_json, batch_lock
from engine import Content, StoryEngine
from engine.content import ROOT
from engine.probability import probabilities
from engine.variants import references
from tools.generate_audio import generation_parser, main as generate

MAX_CHARS = 300
PAUSE_MS = 150
VOICE = ROOT / 'chatterbox/Recording.wav'
CFG_WEIGHT = 0.30
EXAGGERATION = 0.40
READ_KEYS = ('flag', 'ally', 'inventory', 'min_success', 'min_complication', 'min_failure')


def parser():
    result = generation_parser(include_comparison=False)
    result.description = __doc__
    result.set_defaults(chunk_chars=MAX_CHARS, pause_ms=PAUSE_MS, voice=VOICE,
                        cfg_weight=CFG_WEIGHT, exaggeration=EXAGGERATION,
                        linguistic=True, skip_verification=True, device='cpu',
                        scene=None, limit=None, output_dir=None,
                        cache_dir=ROOT / 'audio/experiments/cages/cache')
    result.add_argument('--hero', help='Limiter à un héros : knight, mage, explorer, keeper, rogue')
    result.add_argument('--location', help='Limiter à un lieu : forest, castle, mountain, city, ruins')
    result.add_argument('--item', help='Limiter à un objet : sword, book, amulet, compass, key')
    result.add_argument('--plot', choices=('quiet', 'visitor', 'departure'), help='Limiter à une des trois trames')
    result.add_argument('--scene', action='append', help='Limiter à un ID de scène ; option répétable')
    result.add_argument('--limit', type=int, help='Petit lot de WAV, par exemple 1 ; les WAV déjà prêts sont comptés')
    result.add_argument('--verify', dest='skip_verification', action='store_false', help='Activer le contrôle Whisper')
    return result


def future_reads(content):
    """États lus par les scènes restantes et leurs probabilités.

    Les rangs augmentent strictement. Garder les références de tous les rangs
    suivants est conservateur, mais permet de fusionner les passés équivalents.
    """
    scenes = [s for s in content.scenes.values() if s['arc'] == 'cages']
    all_choices = [c for s in scenes for c in s.get('choices', [])]
    all_choices.extend(c for s in scenes for v in s.get('variants', []) for c in v.get('choices', []))
    # Si les trois issues sont toujours possibles, une différence de probabilité
    # ne change pas le catalogue audio. Éviter de conserver ces flags inutilement.
    all_outcomes_possible = (0 < content.config['probability_min'] <= content.config['probability_max'] < 1
                            and all(0 < c.get('complication_share', .30) < 1 for c in all_choices))
    needed = {k: set() for k in READ_KEYS}
    for ending in content.arcs['cages']['endings']:
        references(ending.get('when', {}), needed)
    result = {}
    for rank in sorted({s['rank'] for s in scenes}, reverse=True):
        for scene in (s for s in scenes if s['rank'] == rank):
            references(scene.get('conditions', {}), needed)
            choices = list(scene.get('choices', []))
            for variant in scene.get('variants', []):
                references(variant.get('when', {}), needed)
                choices.extend(variant.get('choices', []))
            if not all_outcomes_possible:
                for choice in choices:
                    for modifier in choice.get('modifiers', []):
                        references(modifier.get('when', {}), needed)
        result[rank] = {k: frozenset(v) for k, v in needed.items()}
    return result


def future_key(engine, needed):
    state = engine.state
    sets = tuple(frozenset(getattr(state, field) & needed[key])
                 for key, field in (('flag', 'flags'), ('ally', 'allies'), ('inventory', 'inventory')))
    counts = tuple(min(getattr(state, k.removeprefix('min_') + '_count'), max(needed[k], default=0))
                   for k in ('min_success', 'min_complication', 'min_failure'))
    # Les variantes courantes peuvent changer les choix puis enlever un flag.
    # Elles restent dans la clé même si l'état après entrée ne les distingue plus.
    return engine.current['id'], tuple(engine.current['selected_variants']), sets, counts


def fork(engine):
    branch = copy.copy(engine)
    branch.state = copy.copy(engine.state)
    for field in ('flags', 'allies', 'inventory', 'visited_locations', 'met_characters', 'enemies'):
        setattr(branch.state, field, set(getattr(engine.state, field)))
    branch.state.previous_outcomes, branch.state.events = [], []
    branch.journal = {**engine.journal, 'scenes': [], 'choices': []}
    branch.pending = None
    return branch


class FixedRoll:
    def __init__(self, roll):
        self.roll = roll

    def random(self):
        return self.roll


def rolls(choice, engine):
    distribution = probabilities(choice, engine.state, engine.content.config)
    lower = 0.0
    for outcome, upper in (('success', distribution['success']),
                           ('complication', distribution['objective']), ('failure', 1.0)):
        if upper > lower:
            yield outcome, (lower + upper) / 2
        lower = upper


def encounter_seeds(content):
    # Le conte actuel n'utilise pas de personnage tiré dans le catalogue commun.
    # Si un texte s'y réfère plus tard, couvrir chaque rencontre sans modifier le moteur.
    sources = [content.arcs['cages'], [s for s in content.scenes.values() if s['arc'] == 'cages'],
               content.catalog.get('text_values', {}), list(content.heroes.values()),
               list(content.locations.values()), list(content.items.values())]
    if '{encounter_' not in json.dumps(sources, ensure_ascii=False):
        return [0]
    remaining = {e['id'] for e in content.catalog['encounters']}
    result = []
    for seed in itertools.count():
        selected = random.Random(seed).choice(content.catalog['encounters'])['id']
        if selected in remaining:
            result.append(seed)
            remaining.remove(selected)
        if not remaining:
            return result


def iter_cages_records(args, content=None, progress=None):
    """Explorer les vrais choix/issues, exporter le texte avant fusion des états.

    Les conséquences et questions sont déjà assemblées par StoryEngine. Les
    variantes impossibles ne sont pas synthétisées ; un texte identique n'est
    exporté qu'une fois, même s'il apparaît dans plusieurs configurations.
    """
    content = content or Content()
    selectors = []
    for name, catalog in (('hero', content.heroes), ('location', content.locations), ('item', content.items)):
        value = getattr(args, name)
        if value and value not in catalog:
            raise ValueError(f'--{name} inconnu : {value}. Valeurs : {", ".join(catalog)}')
        selectors.append([value] if value else list(catalog))
    scenes = {k: s for k, s in content.scenes.items() if s['arc'] == 'cages'}
    if args.scene and set(args.scene) - scenes.keys():
        raise ValueError('Scène absente de La Maison aux Sept Cages : ' + ', '.join(sorted(set(args.scene) - scenes.keys())))
    relevant = future_reads(content)
    plots = [args.plot] if args.plot else [r['id'] for r in content.arcs['cages']['revelations']]
    seeds = encounter_seeds(content)
    output_root = (args.output_dir or content.root / content.config['audio_root']).resolve()
    seen, counts = set(), {}
    total = len(selectors[0]) * len(selectors[1]) * len(selectors[2])
    for number, triple in enumerate(itertools.product(*selectors), 1):
        if progress and (number == 1 or number % 25 == 0 or number == total):
            progress(f'Préparation des textes : configuration {number}/{total} ({", ".join(triple)}).')
        for plot, seed in itertools.product(plots, seeds):
            queue = deque([StoryEngine(content, *triple, seed=seed, arc_id='cages', revelation_id=plot)])
            expanded = set()
            while queue:
                engine = queue.popleft()
                scene = engine.current
                key = scene['segment_id']
                if key not in seen:
                    seen.add(key)
                    if not args.scene or scene['id'] in args.scene:
                        counts[scene['id']] = counts.get(scene['id'], 0) + 1
                        target = output_root / (key + '.wav')
                        yield dict(segment_id=key, scene_id=scene['id'], role='narration',
                                   text=scene['spoken_text'], target=target, output_file=str(target),
                                   estimated_seconds=scene['estimated_duration'], scene_number=scene['rank'],
                                   title=scene['title'], variant_number=counts[scene['id']])
                state_key = future_key(engine, relevant[scene['rank']])
                if engine.finished or state_key in expanded:
                    continue
                expanded.add(state_key)
                if scene['kind'] == 'intro':
                    branch = fork(engine)
                    branch.advance()
                    queue.append(branch)
                    continue
                for index, choice in enumerate(scene['choices']):
                    for outcome, roll in rolls(choice, engine):
                        branch = fork(engine)
                        branch.rng = FixedRoll(roll)
                        result = branch.choose(index)
                        if result['outcome'] != outcome:
                            raise ValueError('Issue explorée différente du résultat du moteur.')
                        branch.advance()
                        queue.append(branch)


def reuse_model_revision(args):
    """Réutiliser les mêmes poids que la Passeuse si le nouveau cache est vide."""
    if args.model_dir is not None or args.model_revision is not None:
        return
    source = ROOT / 'audio/experiments/passeuse_ch1/cache/model_revision.json'
    if not source.is_file():
        return
    info = Content.read(source)
    if info.get('repo') != 'ResembleAI/chatterbox' or info.get('variant') != 'v3' or not info.get('revision'):
        raise ValueError('Révision Chatterbox de la Passeuse incompatible.')
    target = args.cache_dir / 'model_revision.json'
    with batch_lock(args.cache_dir / '.model.lock'):
        if not target.is_file():
            atomic_json(target, info)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.limit is not None and args.limit < 1:
            raise ValueError('--limit doit être positif.')
        content = Content()
        print('La Maison aux Sept Cages | préparation du lot audio')
        print(f'Voix : {args.voice} | MAX_CHARS = {args.chunk_chars} | PAUSE_MS = {args.pause_ms}')
        catalog = iter_cages_records(args, content, progress=print)
        records = list(itertools.islice(catalog, args.limit)) if args.limit else list(catalog)
        args.plan_output = args.plan_output or ROOT / 'reports/cages_audio/plan.json'
        print(f'{len(records)} textes distincts sélectionnés. WAV : {args.output_dir or content.root / content.config["audio_root"]}')
        print('Les WAV et blocs intègres seront conservés. Ctrl+C interrompt ; la même commande reprend.')
        if not args.dry_run:
            reuse_model_revision(args)
        return generate(args=args, records=records)
    except KeyboardInterrupt:
        print('\nArrêt demandé. Relancer la même commande pour reprendre.', file=sys.stderr)
        return 130
    except Exception as exc:
        print(f'Arrêt : {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
