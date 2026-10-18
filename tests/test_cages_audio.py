import copy
import itertools
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine import Content, StoryEngine
from engine.content import segment_id
from engine.probability import probabilities
from tests.test_tts_batch import FakeVoice
from tools.generate_book_audio import parser as book_parser
from tools.generate_cages_audio import FixedRoll, iter_cages_records, main, parser, reuse_model_revision


class CagesAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content()
        cls.args = parser().parse_args(['--hero', 'explorer', '--location', 'forest', '--item', 'compass'])
        cls.records = list(iter_cages_records(cls.args, cls.content))

    def test_same_voice_and_parameters_as_the_validated_book_setup(self):
        tale, book = parser().parse_args([]), book_parser().parse_args([])
        for field in ('voice', 'chunk_chars', 'pause_ms', 'exaggeration', 'cfg_weight', 'temperature',
                      'seed', 'device', 'linguistic', 'skip_verification', 'compare_single_take'):
            self.assertEqual(getattr(tale, field), getattr(book, field), field)
        first = next(iter_cages_records(tale, self.content))
        self.assertEqual(first['target'].parent, (self.content.root / self.content.config['audio_root']).resolve())
        self.assertEqual(first['target'].name, first['segment_id'] + '.wav')

    def test_catalog_covers_all_plots_mixed_choices_and_outcomes(self):
        catalog = {r['segment_id']: r['text'] for r in self.records}
        self.assertEqual(len(catalog), len(self.records))
        self.assertTrue(all(r['scene_id'].startswith('cages_') and '{' not in r['text'] for r in self.records))
        self.assertEqual({r['scene_id'] for r in self.records},
                         {s['id'] for s in self.content.scenes.values() if s['arc'] == 'cages'})
        rng = random.Random(20261011)
        for plot in ('quiet', 'visitor', 'departure'):
            for trial in range(60):
                engine = StoryEngine(self.content, 'explorer', 'forest', 'compass', trial, 'cages', revelation_id=plot)
                while True:
                    self.assertEqual(catalog[engine.current['segment_id']], engine.current['spoken_text'])
                    if engine.finished:
                        break
                    if engine.current['kind'] == 'intro':
                        engine.advance()
                    else:
                        engine.rng = FixedRoll(0 if trial == 0 else .99999 if trial == 1 else rng.random())
                        result = engine.choose(rng.randrange(2))
                        engine.advance()
                        self.assertTrue(engine.current['spoken_text'].startswith(result['text'] + '\n\n'))

    def test_pruning_matches_exhaustive_paths_with_delayed_flags_and_counts(self):
        content = copy.deepcopy(self.content)
        intro, first, second, ending = [copy.deepcopy(content.scenes[k])
                                        for k in ('cages_intro', 'cages_1', 'cages_2', 'cages_end_pending')]
        intro['variants'], intro['effects'] = [], {}
        intro['text'] = 'Une ouverture.'
        second['text'] = 'Un passage {memory}.'
        second['variants'] = [
            {'id': 'remembered', 'when': {'flag': 'remember'}, 'values': {'memory': 'retrouvé'},
             'effects': {'unset_flags': ['remember']}},
            {'id': 'counted', 'when': {'min_success': 1}, 'append': 'Le succès a laissé une trace.'}]
        content.arcs['cages']['text_values']['memory'] = 'oublié'
        ending['text'], ending['variants'], ending['rank'] = 'Une fin.', [], 3
        first['effects'], first['variants'], first['text'] = {}, [], 'Un premier choix.'
        for index, scene in enumerate((first, second)):
            for choice in scene['choices']:
                choice['modifiers'], choice['effects'] = [], {}
                for name, outcome in choice['outcomes'].items():
                    outcome['next'] = second['id'] if index == 0 else '$ending'
                    outcome['effects'] = {'set_flags': ['remember']} if index == 0 and name == 'success' else {}
                    outcome['text'] = f'Conséquence {choice["id"]} {name}' + (' {memory}.' if index else '.')
        intro['next'] = first['id']
        content.scenes = {s['id']: s for s in (intro, first, second, ending)}
        content.arcs['cages'].update(decision_count=2, endings=[{'scene': ending['id'], 'when': {}}])
        args = parser().parse_args(['--hero', 'explorer', '--location', 'forest', '--item', 'compass', '--plot', 'quiet'])
        actual = {r['segment_id']: r['text'] for r in iter_cages_records(args, content)}
        expected = {}
        for route in itertools.product(itertools.product((0, 1), ('success', 'complication', 'failure')), repeat=2):
            engine = StoryEngine(content, 'explorer', 'forest', 'compass', 0, 'cages', revelation_id='quiet')
            expected[engine.current['segment_id']] = engine.current['spoken_text']
            engine.advance()
            expected[engine.current['segment_id']] = engine.current['spoken_text']
            for index, outcome in route:
                distribution = probabilities(engine.current['choices'][index], engine.state, content.config)
                lower, upper = {'success': (0, distribution['success']),
                                'complication': (distribution['success'], distribution['objective']),
                                'failure': (distribution['objective'], 1)}[outcome]
                engine.rng = FixedRoll((lower + upper) / 2)
                engine.choose(index)
                engine.advance()
                expected[engine.current['segment_id']] = engine.current['spoken_text']
        self.assertEqual(actual, expected)

    def test_dry_run_and_filters_do_not_load_tts_or_create_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.dict('sys.modules', {'torch': None, 'chatterbox': None}), patch('builtins.print'):
                self.assertEqual(main(['--dry-run', '--limit', '1', '--output-dir', str(root/'files'),
                                       '--cache-dir', str(root/'cache'), '--plan-output', str(root/'plan.json')]), 0)
                self.assertEqual(main(['--dry-run', '--hero', 'absent']), 1)
                self.assertEqual(main(['--dry-run', '--scene', 'passeuse_1_01']), 1)
                self.assertEqual(main(['--dry-run', '--limit', '0']), 1)
            plan = json.loads((root/'plan.json').read_text(encoding='utf-8'))
            self.assertEqual(len(plan['segments']), 1)
            self.assertTrue(all(c['characters'] <= 300 for c in plan['segments'][0]['chunks']))
            self.assertFalse(plan['whisper'] or plan['compare_single_take'])
            self.assertFalse((root/'files').exists() or (root/'cache').exists())
        filtered = list(iter_cages_records(parser().parse_args([
            '--hero', 'explorer', '--location', 'forest', '--item', 'compass', '--scene', 'cages_end_full']), self.content))
        self.assertTrue(filtered)
        self.assertTrue(all(r['scene_id'] == 'cages_end_full' for r in filtered))

    def test_generation_resumes_with_one_voice_load_and_no_whisper(self):
        with tempfile.TemporaryDirectory() as folder:
            root, voice = Path(folder), FakeVoice()
            reference = root/'voice.wav'
            reference.write_bytes(b'reference for fake TTS')
            args = ['--limit', '1', '--voice', str(reference), '--cache-dir', str(root/'cache'),
                    '--output-dir', str(root/'files'), '--plan-output', str(root/'plan.json')]
            with patch('audio.chatterbox_backend.environment_identity', return_value={'versions': {}}), \
                 patch('audio.chatterbox_backend.choose_device', return_value='cpu'), \
                 patch('audio.chatterbox_backend.prepare_model', return_value=(root, {'model': 'test-v3'})), \
                 patch('audio.chatterbox_backend.ChatterboxBackend', return_value=voice) as factory, \
                 patch('audio.speech_verification.prepare_asr', side_effect=AssertionError('Whisper reste facultatif')), \
                 patch('builtins.print'):
                self.assertEqual(main(args), 0)
                calls = len(voice.calls)
                self.assertEqual(main(args), 0)
            self.assertEqual(factory.call_count, 1)
            self.assertEqual(len(voice.calls), calls)
            self.assertTrue(all(len(text) <= 300 for text, seed in voice.calls))
            plan = json.loads((root/'plan.json').read_text(encoding='utf-8'))
            segment = plan['segments'][0]
            self.assertEqual(segment['segment_id'], segment_id(segment['scene_id'], 'narration', segment['text']))
            self.assertTrue(Path(segment['output_file']).is_file())

    def test_model_revision_reuses_the_book_pin_without_overriding_existing_or_explicit_choices(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root/'audio/experiments/passeuse_ch1/cache/model_revision.json'
            source.parent.mkdir(parents=True)
            info = dict(repo='ResembleAI/chatterbox', variant='v3', revision='same-model')
            source.write_text(json.dumps(info), encoding='utf-8')
            args = parser().parse_args(['--cache-dir', str(root/'cache')])
            with patch('tools.generate_cages_audio.ROOT', root):
                reuse_model_revision(args)
                target = args.cache_dir/'model_revision.json'
                self.assertEqual(json.loads(target.read_text()), info)
                target.write_text(json.dumps({**info, 'revision': 'already-pinned'}))
                reuse_model_revision(args)
                self.assertEqual(json.loads(target.read_text())['revision'], 'already-pinned')
                args.cache_dir = root/'explicit'
                args.model_revision = 'user-model'
                reuse_model_revision(args)
                self.assertFalse(args.cache_dir.exists())


if __name__ == '__main__':
    unittest.main()
