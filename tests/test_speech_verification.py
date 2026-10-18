import json
import tempfile
import unittest
from pathlib import Path

from audio.speech_verification import IncompleteSpeech, SpeechVerifier, compare_transcript, local_model_directory
from audio.tts_batch import Batch, PCM, receipt_path
from tools.audit_audio import audit
from tests.test_tts_batch import FakeVoice, record


class TranscriptTests(unittest.TestCase):
    def test_full_audio_uses_vad_without_prompt_and_still_refuses_a_missing_ending(self):
        from types import SimpleNamespace
        expected = 'Choix 1 : Montrer la balle. Ou choix 2 : Raconter sa chute dans la fontaine.'
        calls = []
        class Recognizer:
            text = expected
            def transcribe(self, stream, **kwargs):
                calls.append(kwargs)
                return iter([SimpleNamespace(text=self.text)]),None
        verifier = SpeechVerifier.__new__(SpeechVerifier)
        verifier.model = Recognizer()
        pcm = PCM(24000,b'\0\0'*24000)
        result = verifier.verify(expected,pcm,vad_filter=True)
        self.assertTrue(result['passed'])
        self.assertTrue(result['vad_filter'])
        self.assertNotIn('initial_prompt',calls[-1])
        self.assertIs(calls[-1]['vad_filter'],True)
        verifier.model.text = expected.rsplit(' ',1)[0]
        with self.assertRaises(IncompleteSpeech):
            verifier.verify(expected,pcm,vad_filter=True)

    def test_missing_local_tokenizer_is_rejected_before_implicit_download(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('config.json','model.bin'):
                (root/name).write_bytes(b'test')
            with self.assertRaisesRegex(ValueError,'tokenizer.json'):
                local_model_directory(root)

    def test_complete_local_model_directory_is_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('config.json','model.bin','tokenizer.json'):
                (root/name).write_bytes(b'test')
            self.assertEqual(local_model_directory(root),root.resolve())

    def test_french_punctuation_accents_and_choice_numbers_are_normalized(self):
        expected = "Que fais-tu ? Choix 1 : Ouvrir l'entrée protégée. Ou choix 2 : Revenir à Clairval."
        heard = "Que fais tu, choix un, ouvrir l'entrée protégée. Ou choix deux, revenir à Clairval."
        result = compare_transcript(expected,heard)
        self.assertTrue(result['passed'])
        self.assertTrue(result['tail_matched'])
        self.assertEqual(result['word_error_rate'],0)

    def test_missing_last_word_is_rejected_despite_high_global_coverage(self):
        expected = ' '.join(['Le sentier permet de rejoindre le village en toute sécurité.']*8)
        cut = expected.rsplit(' ',1)[0]
        with self.assertRaises(IncompleteSpeech) as error:
            compare_transcript(expected,cut)
        self.assertLess(error.exception.report['word_error_rate'],0.15)
        self.assertFalse(error.exception.report['tail_matched'])

    def test_choice_homophones_from_asr_are_accepted_only_as_numbered_announcements(self):
        expected = 'Que doit faire la princesse ? Choix 1 : Montrer la balle. Ou choix 2 : Raconter sa chute dans la fontaine.'
        heard = expected.replace('Choix 1','Chois 1').replace('choix 2','chois 2')
        result = compare_transcript(expected,heard)
        self.assertTrue(result['choices_matched'])
        self.assertEqual(result['word_error_rate'],0)
        self.assertEqual(result['choice_homophones_normalized'],2)
        for invalid in (heard.replace('Chois 1 : Montrer la balle. ',''),
                        heard.replace('chois 2','chois 1'),
                        heard.replace('chois 2','puis 2'),
                        heard.rsplit(' ',1)[0], heard+' '+heard):
            with self.subTest(invalid=invalid), self.assertRaises(IncompleteSpeech):
                compare_transcript(expected,invalid)

    def test_missing_choice_one_is_rejected_even_with_correct_ending(self):
        expected = 'La scène continue avec des détails utiles. '*10 + 'Que fais-tu ? Choix 1 : Entrer. Ou choix 2 : Attendre près de la porte.'
        heard = expected.replace('Choix 1 : Entrer. ','')
        with self.assertRaises(IncompleteSpeech) as error:
            compare_transcript(expected,heard)
        self.assertTrue(error.exception.report['tail_matched'])
        self.assertFalse(error.exception.report['choices_matched'])

    def test_silence_wrong_text_repetition_and_missing_choice_two_are_rejected(self):
        expected = 'Que fais-tu ? Choix 1 : Entrer dans la salle. Ou choix 2 : Rester près du mur.'
        for heard in ('','Merci de votre attention.',expected.split('Ou choix 2')[0],expected+' '*2+expected):
            with self.subTest(heard=heard):
                with self.assertRaises(IncompleteSpeech):
                    compare_transcript(expected,heard)


class FakeVerifier:
    def __init__(self, cut_first=0, reject_longer_than=None, always_cut=False):
        self.calls = []
        self.cut_first, self.reject_longer_than, self.always_cut = cut_first, reject_longer_than, always_cut

    def verify(self, expected, pcm):
        self.calls.append(expected)
        cut = self.always_cut or len(self.calls) <= self.cut_first or (
            self.reject_longer_than is not None and len(expected) > self.reject_longer_than)
        heard = expected.rsplit(' ',1)[0] if cut else expected
        return compare_transcript(expected,heard)


class ProductionSpeechTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.recipe = {'voice':'test','model':'test'}
        self.cache = self.root/'cache'

    def tearDown(self):
        self.temporary.cleanup()

    def batch(self, voice, verifier, policy='test-v1', **kwargs):
        return Batch(self.cache,self.recipe,lambda:voice,verifier_factory=lambda:verifier,
                     verifier_identity={'policy':policy},progress=lambda _:None,**kwargs)

    def test_early_stops_are_retried_with_new_seeds_and_only_complete_take_is_saved(self):
        item = record(self.root,'Le chemin mène vers un petit village tranquille.')
        voice, verifier = FakeVoice(), FakeVerifier(cut_first=2)
        batch = self.batch(voice,verifier)
        stats = batch.run([item])
        self.assertEqual(len(voice.calls),3)
        self.assertEqual(len({seed for _,seed in voice.calls}),3)
        self.assertEqual(stats['retry_attempts'],2)
        self.assertTrue(audit([item])['ready'])
        receipt = json.loads(receipt_path(item['target']).read_text(encoding='utf-8'))
        self.assertTrue(receipt['verification']['passed'])

    def test_failed_speech_is_never_marked_ready_and_shared_failure_is_not_generated_repeatedly(self):
        text = 'Un passage partagé qui doit être lu jusqu’au dernier mot.'
        items = [record(self.root,text,'a'),record(self.root,text,'b')]
        voice = FakeVoice()
        stats = self.batch(voice,FakeVerifier(always_cut=True)).run(items)
        self.assertEqual(len(voice.calls),3)
        self.assertEqual(stats['failed'],2)
        self.assertFalse(any(r['target'].exists() for r in items))
        self.assertFalse(audit(items)['ready'])
        reports = list(self.cache.glob('*/rejected/*/attempt_*.json'))
        self.assertEqual(len(reports),3)
        self.assertFalse(json.loads(reports[0].read_text(encoding='utf-8'))['verification']['passed'])

    def test_shorter_subpassages_are_checked_separately_and_resume_uses_their_proof(self):
        text = ('Tu observes le sentier près du mur et prépares le retour. '
                'Tu regardes les traces avant de choisir une direction. '
                'Tu gardes ton sac au sec et rejoins le prochain abri. '
                'Tu peux maintenant continuer vers le village sans te perdre.')
        item = record(self.root,text)
        voice, verifier = FakeVoice(), FakeVerifier(reject_longer_than=160)
        batch = self.batch(voice,verifier)
        stats = batch.run([item])
        self.assertEqual(stats['generated'],1)
        self.assertGreater(stats['fallback_splits'],0)
        self.assertTrue(audit([item])['ready'])
        calls = len(voice.calls)
        self.assertEqual(self.batch(voice,verifier).run([item])['skipped'],1)
        self.assertEqual(len(voice.calls),calls)

    def test_old_format_only_audio_is_rechecked_without_synthesizing_again(self):
        item = record(self.root,'Un passage complet avec une fin bien présente.')
        Batch(self.cache,self.recipe,lambda:FakeVoice(),progress=lambda _:None).run([item])
        self.assertFalse(audit([item])['ready'])
        def forbidden():
            self.fail('Le TTS ne doit pas être refait pour revalider une voix correcte.')
        batch = Batch(self.cache,self.recipe,forbidden,verifier_factory=lambda:FakeVerifier(),
                      verifier_identity={'policy':'asr-added'},progress=lambda _:None)
        stats = batch.run([item])
        self.assertEqual(stats['chunks_generated'],0)
        self.assertEqual(stats['speech_checks'],1)
        self.assertTrue(audit([item])['ready'])

    def test_new_recognition_policy_rechecks_audio_without_invalidating_voice_cache(self):
        item = record(self.root,'Une scène complète que l’on peut vérifier de nouveau.')
        voice, first = FakeVoice(), FakeVerifier()
        original = self.batch(voice,first,policy='small')
        original.run([item])
        second = FakeVerifier()
        upgraded = self.batch(voice,second,policy='medium')
        self.assertEqual(original.profile,upgraded.profile)
        upgraded.run([item])
        self.assertEqual(len(voice.calls),1)
        self.assertEqual(len(second.calls),1)

    def test_restart_after_failed_attempts_uses_a_new_seed(self):
        item = record(self.root,'Une phrase dont la fin doit être clairement prononcée.')
        voice = FakeVoice()
        self.batch(voice,FakeVerifier(always_cut=True),attempts=1).run([item])
        first_seed = voice.calls[0][1]
        self.batch(voice,FakeVerifier(),attempts=1).run([item])
        self.assertNotEqual(first_seed,voice.calls[1][1])
        self.assertTrue(audit([item])['ready'])

    def test_rejected_recheck_removes_old_ready_status(self):
        item = record(self.root,'Une ancienne prise dont la fin doit être revérifiée.')
        voice = FakeVoice()
        self.batch(voice,FakeVerifier(),policy='small').run([item])
        self.assertTrue(audit([item])['ready'])
        stats = self.batch(voice,FakeVerifier(always_cut=True),policy='medium').run([item])
        self.assertEqual(stats['failed'],1)
        self.assertTrue(item['target'].exists())
        report = audit([item])
        self.assertTrue(report['format_ready'])
        self.assertFalse(report['ready'])
        self.assertEqual(report['speech_unverified'],1)


if __name__ == '__main__':
    unittest.main()
