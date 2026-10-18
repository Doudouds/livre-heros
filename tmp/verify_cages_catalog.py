"""Comparer le plan complet aux passages du vrai moteur, sans synthèse."""
import itertools
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import Content, StoryEngine
from engine.content import segment_id
from tools.generate_cages_audio import FixedRoll

plan = json.loads((ROOT/'reports/cages_audio/plan.json').read_text(encoding='utf-8'))
catalog = {r['segment_id']: r for r in plan['segments']}
assert len(catalog) == len(plan['segments'])
for record in catalog.values():
    assert record['segment_id'] == segment_id(record['scene_id'], 'narration', record['text'])
    assert Path(record['output_file']) == ROOT/'audio/files'/(record['segment_id']+'.wav')
    assert ' '.join(c['text'] for c in record['chunks']) == ' '.join(record['text'].split())
    assert all(c['characters'] <= 300 for c in record['chunks'])

content, rng = Content(), random.Random(20261011)
checked, sessions = 0, 0
for triple in itertools.product(content.heroes, content.locations, content.items):
    for plot in ('quiet', 'visitor', 'departure'):
        for trial in range(3):
            engine = StoryEngine(content, *triple, seed=trial, arc_id='cages', revelation_id=plot)
            while True:
                assert catalog[engine.current['segment_id']]['text'] == engine.current['spoken_text']
                checked += 1
                if engine.finished:
                    break
                if engine.current['kind'] == 'intro':
                    engine.advance()
                else:
                    engine.rng = FixedRoll(0 if trial == 0 else .99999 if trial == 1 else rng.random())
                    engine.choose(rng.randrange(2))
                    engine.advance()
            sessions += 1
result = dict(segments=len(catalog), scenes=len({r['scene_id'] for r in catalog.values()}),
              distinct_chunks=len({c['text'] for r in catalog.values() for c in r['chunks']}),
              checked_sessions=sessions, checked_spoken_texts=checked,
              max_chars=plan['max_chars'], pause_ms=plan['pause_ms'],
              chatterbox_generation_started=False)
(ROOT/'reports/cages_audio/catalog_validation.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
