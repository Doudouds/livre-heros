import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from audio.tts_batch import (Batch, PCM, atomic_wave, batch_lock, file_hash, read_manifest,
                             read_wave, receipt_matches, receipt_path, split_text)
from engine.content import segment_id
from tools.generate_audio import main


class FakeVoice:
    def __init__(self, crash_on=None, fail_on=None):
        self.calls = []
        self.crash_on, self.fail_on = crash_on, fail_on

    def synthesize(self, text, seed):
        self.calls.append((text, seed))
        if len(self.calls) == self.crash_on:
            raise KeyboardInterrupt()
        if self.fail_on and self.fail_on in text:
            raise RuntimeError('échec simulé')
        return PCM(8000, b'\x01\x00' * 1600)


def record(root, text, scene='test_1'):
    key = segment_id(scene, 'narration', text)
    return dict(segment_id=key, scene_id=scene, role='narration', text=text,
                output_file=f'audio/files/{key}.wav', target=root / 'audio/files' / (key + '.wav'),
                estimated_seconds=10)


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.cache = self.root / 'cache'
        self.recipe = {'voice_sha256':'voix-A','model':'v3-test','language':'fr'}

    def tearDown(self):
        self.directory.cleanup()

    def batch(self, fake=None, recipe=None, **kwargs):
        fake = fake or FakeVoice()
        return Batch(self.cache, recipe or self.recipe, lambda: fake, progress=lambda _: None, **kwargs)

    def test_keyboard_interrupt_resumes_inside_scene_without_losing_first_chunk(self):
        text = 'Le premier passage est terminé.\n\nLe deuxième reste à faire.\n\nQue fais-tu ? Choix 1 : Entrer. Ou choix 2 : Attendre.'
        item = record(self.root, text)
        fake = FakeVoice(crash_on=2)
        batch = self.batch(fake)
        with self.assertRaises(KeyboardInterrupt):
            batch.run([item])
        self.assertFalse(item['target'].exists())
        cached = list(self.cache.glob('*/chunks/*.wav'))
        self.assertEqual(len(cached), 1)
        before = file_hash(cached[0])
        resumed = FakeVoice()
        stats = self.batch(resumed).run([item])
        self.assertEqual(stats['generated'], 1)
        self.assertEqual(len(resumed.calls), 2)
        self.assertEqual(stats['chunks_reused'], 1)
        self.assertEqual(before, file_hash(cached[0]))
        self.assertIn('Ou choix 2', resumed.calls[-1][0])
        self.assertEqual(len(read_wave(item['target']).frames), 3*3200 + 2*1280*2)

    def test_shared_paragraphs_generated_once_and_completed_run_never_loads_model(self):
        items = [record(self.root, 'Un passage commun.\n\nUne fin différente.', 'a'),
                 record(self.root, 'Un passage commun.\n\nUne autre fin.', 'b')]
        fake = FakeVoice()
        stats = self.batch(fake).run(items)
        self.assertEqual(len(fake.calls), 3)
        self.assertEqual(stats['chunks_reused'], 1)
        batch = Batch(self.cache, self.recipe, lambda: self.fail('Le modèle ne doit pas être chargé'), progress=lambda _: None)
        self.assertEqual(batch.run(items)['skipped'], 2)

    def test_crash_between_final_wav_and_receipt_recovers_automatically(self):
        item = record(self.root, 'Une scène.\n\nQue fais-tu ? Choix 1 : Partir. Ou choix 2 : Rester.')
        from audio import tts_batch
        original = tts_batch.write_receipt
        def crash(path, *args, **kwargs):
            if path == item['target']:
                raise KeyboardInterrupt()
            return original(path, *args, **kwargs)
        with patch('audio.tts_batch.write_receipt', side_effect=crash):
            with self.assertRaises(KeyboardInterrupt):
                self.batch().run([item])
        self.assertTrue(item['target'].exists())
        self.assertFalse(receipt_path(item['target']).exists())
        resumed = Batch(self.cache, self.recipe, lambda: self.fail('Passages déjà en cache'), progress=lambda _: None)
        self.assertEqual(resumed.run([item])['generated'], 1)
        self.assertTrue(receipt_matches(item['target'], resumed.identity(item)))

    def test_truncated_final_audio_is_reassembled_from_verified_chunks(self):
        item = record(self.root, 'Un récit complet.')
        self.batch().run([item])
        item['target'].write_bytes(item['target'].read_bytes()[:48])
        batch = Batch(self.cache, self.recipe, lambda: self.fail('Cache conservé'), progress=lambda _: None)
        self.assertEqual(batch.run([item])['generated'], 1)
        self.assertEqual(len(read_wave(item['target']).frames), 3200)

    def test_corrupt_chunk_is_regenerated_when_final_requires_rebuilding(self):
        item = record(self.root, 'Une scène.\n\nUne conclusion.')
        self.batch().run([item])
        list(self.cache.glob('*/chunks/*.wav'))[0].write_bytes(b'corrompu')
        item['target'].write_bytes(b'corrompu')
        fake = FakeVoice()
        stats = self.batch(fake).run([item])
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(stats['chunks_reused'], 1)

    def test_voice_change_is_refused_before_any_output_is_modified(self):
        existing = record(self.root, 'Déjà terminé.', 'existing')
        new = record(self.root, 'Encore à faire.', 'new')
        self.batch().run([existing])
        original = file_hash(existing['target'])
        with self.assertRaisesRegex(ValueError, 'Voix/modèle'):
            self.batch(recipe={**self.recipe,'voice_sha256':'voix-B'}).run([new,existing])
        self.assertFalse(new['target'].exists())
        self.assertEqual(file_hash(existing['target']), original)
        stats = self.batch(recipe={**self.recipe,'voice_sha256':'voix-B'},overwrite=True).run([existing])
        self.assertEqual(stats['generated'], 1)

    def test_unmanaged_wav_is_not_silently_replaced(self):
        item = record(self.root, 'Un WAV extérieur.')
        atomic_wave(item['target'], PCM(8000,b'\x01\x00'*1600))
        with self.assertRaisesRegex(ValueError, 'sans reçu'):
            self.batch().run([item])

    def test_segment_failure_preserves_successes_and_continues(self):
        items = [record(self.root, text, str(i)) for i,text in enumerate(('Réussite avant.','Problème simulé.','Réussite après.'))]
        stats = self.batch(FakeVoice(fail_on='Problème')).run(items)
        self.assertEqual(stats['generated'], 2)
        self.assertEqual(stats['failed'], 1)
        events = [json.loads(line) for line in (self.cache / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual([e['status'] for e in events], ['done','failed','done'])
        recovered = self.batch().run(items)
        self.assertEqual(recovered['skipped'], 2)
        self.assertEqual(recovered['generated'], 1)

    def test_concurrent_run_is_refused_and_lock_can_be_reused(self):
        path = self.cache / '.test.lock'
        with batch_lock(path):
            with self.assertRaisesRegex(RuntimeError, 'autre génération'):
                with batch_lock(path):
                    self.fail('Verrou concurrent accepté')
        with batch_lock(path):
            pass

    def test_split_preserves_all_words_and_both_choices(self):
        text = ('Une phrase longue avec beaucoup de mots répétés. ' * 10) + '\n\nQue fais-tu ? Choix 1 : Ouvrir la porte. Ou choix 2 : Suivre le chemin.'
        chunks = split_text(text,80)
        self.assertTrue(all(len(c) <= 80 for c in chunks))
        self.assertEqual(' '.join(chunks).split(),text.split())
        self.assertTrue(' '.join(chunks).endswith('Ou choix 2 : Suivre le chemin.'))

    def test_manifest_refuses_wrong_hash_or_escape_path(self):
        item = record(self.root, 'Bonjour.')
        path = self.root / 'manifest.jsonl'
        clean = {k:v for k,v in item.items() if k != 'target'}
        path.write_text(json.dumps(clean), encoding='utf-8')
        self.assertEqual(read_manifest(path,self.root)[0]['target'],item['target'])
        for mutation in ({'text':'Bonsoir.'},{'output_file':'../extérieur.wav'}):
            path.write_text(json.dumps({**clean,**mutation}),encoding='utf-8')
            with self.assertRaises(ValueError):
                read_manifest(path,self.root)

    def test_dry_run_works_without_torch_or_reference_voice(self):
        item = record(self.root, 'Bonjour.')
        path = self.root / 'manifest.jsonl'
        path.write_text(json.dumps({k:v for k,v in item.items() if k != 'target'}), encoding='utf-8')
        with patch('tools.generate_audio.ROOT',self.root), patch.dict('sys.modules',{'torch':None,'chatterbox':None}), patch('builtins.print'):
            self.assertEqual(main(['--manifest',str(path),'--dry-run']),0)
        self.assertFalse(self.cache.exists())
        self.assertFalse(item['target'].exists())

    def test_audio_audit_detects_missing_corrupt_and_mixed_voice_files(self):
        from tools.audit_audio import audit
        items = [record(self.root,'Scène une.','one'),record(self.root,'Scène deux.','two')]
        self.assertEqual(audit(items)['missing'],2)
        self.batch().run(items)
        self.assertTrue(audit(items)['format_ready'])
        self.assertFalse(audit(items)['ready'])  # Un conteneur valide ne prouve pas les paroles.
        self.batch(recipe={**self.recipe,'voice_sha256':'voix-B'},overwrite=True).run([items[1]])
        self.assertFalse(audit(items)['ready'])
        self.assertEqual(len(audit(items)['profiles']),2)
        items[0]['target'].write_bytes(b'invalide')
        self.assertEqual(audit(items)['invalid'],1)


if __name__ == '__main__':
    unittest.main()
