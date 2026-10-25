import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from audio.speech_verification import IncompleteSpeech, SpeechVerifier, compare_transcript
from audio.tts_batch import Batch, PCM, atomic_json, receipt_path
from audio.verification_evidence import validate_evidence
from engine.content import ROOT
from tests.test_story_audio import Verifier, fake_plan, runner
from tests.test_tts_batch import FakeVoice, record


class SpokenComparisonTests(unittest.TestCase):
    def test_observed_french_homophones_do_not_trigger_false_cutoffs(self):
        pairs = [
            ('Je te rendrai ta balle.','Je te rendrai tabale.'),
            ('Heureux de voir son seigneur délivré.','Heureux de voir son seigneur délivrer.'),
            ('Il répondit sans chercher d’autre excuse.','Il répondit sans chercher d’autres excuses.'),
            ('Elle ne chercha plus de moyen de retarder le départ.',
             'Elle ne cherche à plus de moyens de retarder le départ.'),
            ('La princesse seule pouvait l’en libérer.','La princesse seuls pouvaient l’en libérer.'),
            ('Le lendemain, ils partiraient tous deux pour son royaume.',
             'Le lendemain, il partirait tous deux pour son royaume.'),
        ]
        for expected,heard in pairs:
            with self.subTest(heard=heard):
                result = compare_transcript(expected,heard)
                self.assertTrue(result['tail_matched'])
                self.assertEqual(result['word_error_rate'],0)
                self.assertGreater(result['orthographic_word_error_rate'],0)

    def test_missing_words_changed_words_and_different_sounds_remain_rejected(self):
        pairs = [
            ('Je te rendrai ta balle.','Je te rendrai ta.'),
            ('Je te rendrai ta balle.','Je te rendrai ta pelle.'),
            ('Son seigneur était délivré.','Son seigneur était délivler.'),
            ('Elle regarda une fille.','Elle regarda une file.'),
            ('Elle regarda une fille.','Elle regarda une file file.'),
            ('Il peut parler.','Il peut parle.'),
            ('Il faut écrire choix 1 puis choix 2.','Il faut écrire choix 2 puis choix 1.'),
        ]
        for expected,heard in pairs:
            with self.subTest(heard=heard),self.assertRaises(IncompleteSpeech):
                compare_transcript(expected,heard)

    def test_asr_retries_recognition_before_asking_for_new_speech(self):
        expected = 'La princesse regarde la fontaine.'
        calls = []
        class Model:
            def transcribe(self,stream,**kwargs):
                calls.append(kwargs)
                text = expected.rsplit(' ',1)[0] if len(calls) == 1 else expected
                return iter([SimpleNamespace(text=text)]),None
        verifier = SpeechVerifier.__new__(SpeechVerifier)
        verifier.model = Model()
        result = verifier.verify(expected,PCM(8000,b'\x01\0'*8000))
        self.assertTrue(result['passed'])
        self.assertEqual(len(result['asr_attempts']),2)
        self.assertNotEqual(calls[0]['beam_size'],calls[1]['beam_size'])
        self.assertTrue(all('initial_prompt' not in options for options in calls))

    def test_full_tail_is_rechecked_on_the_end_of_the_actual_assembled_audio(self):
        class VerifierWithTail(SpeechVerifier):
            def __init__(self):
                self.seen = []
            def verify(self,expected,pcm,**kwargs):
                self.seen.append(pcm.frames)
                if len(self.seen) == 1:
                    return compare_transcript(expected,expected+' Bruit.')
                if pcm.frames != b'\x02\0'*8000:
                    return compare_transcript(expected,expected.rsplit(' ',1)[0])
                return compare_transcript(expected,expected)
        pcm = PCM(8000,b'\x01\0'*8000+b'\x02\0'*8000)
        expected = 'La princesse regarde la fontaine. Il lui rendra sa balle.'
        check = VerifierWithTail().verify_complete(expected,pcm,tail_text='Il lui rendra sa balle.',tail_frames=16000)
        self.assertTrue(check['passed'])
        self.assertFalse(check['global_check']['passed'])
        self.assertTrue(check['tail_check']['passed'])
        validate_evidence(expected,check,pcm,tail_text='Il lui rendra sa balle.',
                          tail_pcm=PCM(8000,b'\x02\0'*8000))
        with self.assertRaises(ValueError):
            validate_evidence(expected,check,pcm,tail_text='Il lui rendra sa balle.',
                              tail_pcm=PCM(8000,b'\x03\0'*8000))
        cut = PCM(8000,pcm.frames[:-4000])
        with self.assertRaises(IncompleteSpeech):
            VerifierWithTail().verify_complete(expected,cut,tail_text='Il lui rendra sa balle.',tail_frames=16000)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT/'tmp')
        self.folder = Path(self.temporary.name)
    def tearDown(self):
        self.temporary.cleanup()

    def test_changed_checker_can_recover_rejected_audio_without_loading_tts(self):
        text = 'Le fidèle Henri retrouve son seigneur délivré.'
        item = record(self.folder,text)
        class OldVerifier:
            def verify(self,expected,pcm):
                report = dict(passed=False,reasons=['fin du texte non retrouvée'],
                              transcript=expected,word_error_rate=.05)
                raise IncompleteSpeech(report)
        first = Batch(self.folder/'cache',{'voice':'A'},lambda:FakeVoice(),
                      verifier_factory=lambda:OldVerifier(),verifier_identity={'version':1},
                      attempts=1,progress=lambda message:None)
        self.assertEqual(first.run([item])['failed'],1)
        def forbidden():
            self.fail('Une réécoute ne doit pas charger le TTS.')
        second = Batch(self.folder/'cache',{'voice':'A'},forbidden,allow_synthesis=False,
                       verifier_factory=lambda:Verifier(),verifier_identity={'version':2},
                       progress=lambda message:None)
        self.assertEqual(second.run([item])['failed'],0)
        proof = json.loads(receipt_path(item['target']).read_text(encoding='utf-8'))
        self.assertTrue(proof['verification']['passed'])
        recovered = list((self.folder/'cache').glob('*/chunks/*.wav.json'))
        self.assertTrue(any('recovered_from' in json.loads(p.read_text(encoding='utf-8')) for p in recovered))

    def test_cache_only_mode_never_calls_synthesis_when_no_candidate_exists(self):
        run = runner(self.folder,recheck_only=True,
                     backend_factory=lambda *args:self.fail('Synthèse interdite en réécoute seule.'))
        plan = fake_plan(self.folder)
        self.assertEqual(run.run([plan]),1)
        self.assertFalse(Path(plan['output_file']).exists())

    def test_final_tail_failure_retries_only_last_portion(self):
        plan = fake_plan(self.folder,paragraphs=[
            'La princesse regarde la fontaine.', 'Le fidèle Henri attend devant la voiture.',
            'Le roi se tourna vers la porte.'])
        voice = FakeVoice()
        run = runner(self.folder,voice,Verifier(fail_full=1))
        self.assertEqual(run.run([plan]),0)
        self.assertEqual(len(voice.calls),4)
        self.assertEqual(sum(t == plan['spans'][0]['text'] for t,_ in voice.calls),1)
        self.assertEqual(sum(t == plan['spans'][1]['text'] for t,_ in voice.calls),1)
        self.assertEqual(sum(t == plan['spans'][2]['text'] for t,_ in voice.calls),2)
        self.assertEqual(run.state['segments'][0]['span_rounds'],[0,0,1])

    def test_new_checker_preserves_mixed_portion_rounds_without_synthesis(self):
        plan = fake_plan(self.folder,paragraphs=['Le roi regarde la fenêtre.','La princesse reste près de la porte.'])
        self.assertEqual(runner(self.folder,verifier=Verifier(fail_full=1)).run([plan]),0)
        resumed = runner(self.folder,recheck_only=True,verifier_identity={'checker':'test-v2'},
                         backend_factory=lambda *args:self.fail('Le cache des deux graines doit être réutilisé.'))
        self.assertEqual(resumed.run([plan]),0)
        self.assertEqual(resumed.state['segments'][0]['span_rounds'],[0,1])

    def test_uncertain_global_check_does_not_regenerate_all_validated_portions(self):
        plan = fake_plan(self.folder,paragraphs=['Le roi regarde la fenêtre.','La princesse reste près de la porte.'])
        class Uncertain(Verifier):
            def verify(self,expected,pcm,**kwargs):
                if expected == plan['text']:
                    return compare_transcript(expected,'Un autre texte sans rapport avec le récit.')
                return super().verify(expected,pcm,**kwargs)
        voice = FakeVoice()
        run = runner(self.folder,voice,Uncertain())
        self.assertEqual(run.run([plan]),1)
        self.assertEqual(len(voice.calls),2)
        self.assertFalse(Path(plan['output_file']).exists())


if __name__ == '__main__':
    unittest.main()
