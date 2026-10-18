import copy
import itertools
import json
import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from audio.tts_batch import split_linguistic, read_wave, receipt_path
from engine.book_engine import BookEngine
from engine.content import Content
from tests.test_tts_batch import FakeVoice
from tools.generate_book_audio import all_book_records, book_record, main, parser


class LinguisticSplitTests(unittest.TestCase):
    def test_complete_sentences_and_closing_quotes_stay_together(self):
        text = ('Elle regarda la fenêtre. Puis elle dit : « Le jour se lève ! » '
                'La cloche sonnait.\n\nElle descendit les marches sans attendre.')
        chunks = split_linguistic(text, 80)
        self.assertEqual(' '.join(chunks), ' '.join(text.split()))
        self.assertTrue(all(len(c) <= 80 for c in chunks))
        self.assertTrue(all(c.endswith(('.', '»')) for c in chunks))

    def test_long_sentence_prefers_semicolon_over_word_boundary(self):
        first = 'Elle suivit lentement le chemin près des grands arbres ;'
        second = ' les oiseaux chantaient dans les branches depuis le lever du jour.'
        chunks = split_linguistic(first + second, 80)
        self.assertEqual(chunks, [first, second.strip()])

    def test_abbreviations_and_decimal_numbers_are_not_sentence_endings(self):
        text = 'M. Martin aperçut 3.5 étoiles dans son rêve avant le chant des oiseaux. Ensuite, il se leva.'
        self.assertEqual(split_linguistic(text, 80),
                         [text[:text.index(' Ensuite')], 'Ensuite, il se leva.'])

    def test_long_sentence_without_punctuation_keeps_every_word(self):
        text = ('une très longue phrase sans ponctuation ' * 30).strip()
        chunks = split_linguistic(text, 300)
        self.assertEqual(' '.join(chunks), text)
        self.assertTrue(all(len(c) <= 300 for c in chunks))
        with self.assertRaisesRegex(ValueError, 'mot dépasse'):
            split_linguistic('a' * 301, 300)


class BookAudioTests(unittest.TestCase):
    def test_default_segment_matches_the_current_book_including_both_choices(self):
        args = parser().parse_args(['--dry-run'])
        record = book_record(args)
        engine = BookEngine(Content())
        self.assertEqual(record['text'], engine.current['spoken_text'])
        self.assertEqual(record['segment_id'], engine.current['segment_id'])
        chunks = split_linguistic(record['text'], 300)
        self.assertEqual(' '.join(chunks).split(), record['text'].split())
        self.assertEqual(len(chunks), 6)
        self.assertIn('Ou choix 2 :', chunks[-1])

    def test_later_segment_and_chapter_follow_the_selected_path(self):
        content = Content()
        args = parser().parse_args(['--segment', '2', '--choice', '2'])
        engine = BookEngine(content)
        engine.choose(1)
        engine.advance()
        self.assertEqual(book_record(args, content)['text'], engine.current['spoken_text'])
        chapter = book_record(parser().parse_args(['--chapter', '--choice', '2']), content)
        self.assertIn(engine.current['spoken_text'], chapter['text'])
        self.assertEqual(chapter['scene_id'], 'passeuse_ch1_chapter')
        with self.assertRaises(ValueError):
            book_record(parser().parse_args(['--segment', '29']), content)

    def test_generation_without_whisper_resumes_without_loading_another_backend(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            voice = root / 'voice.wav'
            voice.write_bytes(b'reference for fake TTS')
            fake = FakeVoice()
            argv = ['--voice', str(voice), '--cache-dir', str(root / 'cache'),
                    '--output-dir', str(root / 'files'), '--plan-output', str(root / 'plan.json')]
            with patch('audio.chatterbox_backend.environment_identity', return_value={'versions': {}}), \
                 patch('audio.chatterbox_backend.choose_device', return_value='cpu'), \
                 patch('audio.chatterbox_backend.prepare_model', return_value=(root, {'model': 'test-v3'})), \
                 patch('audio.chatterbox_backend.ChatterboxBackend', return_value=fake) as factory, \
                 patch('audio.speech_verification.prepare_asr', side_effect=AssertionError('Whisper doit rester optionnel')), \
                 patch('builtins.print'):
                self.assertEqual(main(argv), 0)
                self.assertEqual(main(argv), 0)
            self.assertEqual(factory.call_count, 1)
            self.assertEqual(len(fake.calls), 6)
            self.assertTrue(all(len(text) <= 300 for text,_ in fake.calls))
            plan = json.loads((root / 'plan.json').read_text(encoding='utf-8'))
            output = Path(plan['segments'][0]['output_file'])
            # Six prises de 0,2 s et exactement cinq pauses de 150 ms.
            pcm = read_wave(output)
            self.assertAlmostEqual(len(pcm.frames) / 2 / pcm.sample_rate, 1.95)
            receipt = json.loads(receipt_path(output).read_text(encoding='utf-8'))
            self.assertIsNone(receipt['verification'])
            events = [json.loads(line) for line in (root / 'cache/chunk_events.jsonl').read_text(encoding='utf-8').splitlines()]
            chunks = [e for e in events if e.get('type') == 'chunk']
            self.assertEqual(len(chunks), 6)
            self.assertTrue(all(e['status'] == 'done' and e['audio_seconds'] == 0.2 for e in chunks))
            self.assertTrue(all('characters' in e and 'preview' in e for e in chunks))

    def test_catalog_matches_every_path_on_small_book_with_delayed_memory(self):
        book = copy.deepcopy(Content().books['passeuse_ch1'])
        book['scenes'] = book['scenes'][:6]
        book['decision_count'] = 5
        last = book['scenes'][-1]
        last['kind'], last['choices'] = 'ending', []
        for variant in last.get('variants', []):
            variant.pop('choices', None)
        book['scenes'][0]['choices'][0].setdefault('flags', []).append('long_memory')
        last['text'] += '\n\n{late_memory}'
        last['values']['late_memory'] = 'Un souvenir absent.'
        last['variants'].extend([
            {'id':'memory_present', 'when':{'all':['long_memory']}, 'values':{'late_memory':'Un souvenir conservé.'}},
            {'id':'memory_absent', 'when':{'none':['long_memory']}, 'values':{'late_memory':'Un souvenir oublié.'}}])
        last['echoes'] = [{'flag':'long_memory', 'text':'Ce souvenir lui était revenu.'}]
        middle = book['scenes'][3]
        special_choices = copy.deepcopy(middle['choices'])
        special_choices[0]['text'] = 'Tenir compte de son souvenir'
        special_choices[0]['consequence_variants'] = [
            {'when':{'all':['long_memory']}, 'consequence':'Elle conserva le souvenir de son choix.'}]
        middle.setdefault('variants', []).append(
            {'id':'memory_choices', 'when':{'any':['long_memory']}, 'choices':special_choices})
        content = SimpleNamespace(books={'passeuse_ch1':book}, config={'choice_seconds':0}, seconds=lambda text:len(text)/10)
        args = parser().parse_args(['--all-segments', '--dry-run'])
        catalog = all_book_records(args, content)
        expected = {}
        for route in itertools.product((0,1), repeat=5):
            engine = BookEngine(content)
            expected[engine.current['segment_id']] = engine.current['spoken_text']
            for choice in route:
                engine.choose(choice)
                engine.advance()
                expected[engine.current['segment_id']] = engine.current['spoken_text']
        self.assertEqual({r['segment_id']:r['text'] for r in catalog}, expected)
        self.assertEqual(len(catalog), len({r['segment_id'] for r in catalog}))

    def test_full_catalog_covers_mixed_choices_and_preserves_runtime_filenames(self):
        content = Content()
        records = all_book_records(parser().parse_args(['--all-segments']), content)
        catalog = {r['segment_id']:r for r in records}
        self.assertEqual({r['scene_id'] for r in records}, {s['id'] for s in content.books['passeuse_ch1']['scenes']})
        rng = random.Random(20261011)
        for _ in range(40):
            engine = BookEngine(content)
            while True:
                record = catalog[engine.current['segment_id']]
                self.assertEqual(record['text'], engine.current['spoken_text'])
                self.assertEqual(record['target'].name, engine.current['segment_id'] + '.wav')
                if engine.finished:
                    break
                engine.choose(rng.randrange(2))
                engine.advance()

    def test_all_segments_dry_run_does_not_import_tts_or_create_wavs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.dict('sys.modules', {'torch':None, 'chatterbox':None}), patch('builtins.print'):
                self.assertEqual(main(['--all-segments', '--dry-run', '--output-dir', str(root/'files'),
                                       '--plan-output', str(root/'plan.json')]), 0)
            plan = json.loads((root/'plan.json').read_text(encoding='utf-8'))
            self.assertEqual(len(plan['segments']), len(all_book_records(parser().parse_args(['--all-segments']))))
            self.assertFalse(plan['compare_single_take'])
            self.assertTrue(all(s['title'] and s['scene_number'] and s['variant_number'] for s in plan['segments']))
            self.assertFalse((root/'files').exists())


if __name__ == '__main__':
    unittest.main()
