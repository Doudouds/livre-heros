import copy
import unittest

from audio.speech_review import EvictableBackend, ReviewingSpeechVerifier
from audio.speech_verification import compare_transcript
from audio.tts_batch import PCM, recovery_parts


class Reader:
    def __init__(self, reject=False):
        self.reject,self.calls = reject,[]
    def verify(self,expected,pcm,**options):
        self.calls.append((expected,options))
        return compare_transcript(expected,expected.rsplit(' ',1)[0] if self.reject else expected)
    def verify_complete(self,expected,pcm,**options):
        return self.verify(expected,pcm,**options)


class IndependentReviewTests(unittest.TestCase):
    def test_second_model_can_confirm_without_changing_the_speech_threshold(self):
        primary,review = Reader(True),Reader()
        controller = ReviewingSpeechVerifier(lambda:primary,lambda:review,progress=lambda text:None)
        check = controller.verify('La princesse regarde la fontaine.',PCM(8000,b'\1\0'*8000))
        self.assertTrue(check['passed'])
        self.assertTrue(check['independent_review'])
        self.assertFalse(check['primary_rejection']['passed'])
        self.assertEqual(len(primary.calls),1)
        self.assertEqual(len(review.calls),1)

    def test_final_review_cannot_be_approved_by_small_when_medium_rejects(self):
        from audio.speech_verification import IncompleteSpeech
        primary,review = Reader(),Reader(True)
        controller = ReviewingSpeechVerifier(lambda:primary,lambda:review,progress=lambda text:None)
        with self.assertRaises(IncompleteSpeech):
            controller.verify_complete('La princesse regarde la fontaine.',PCM(8000,b'\1\0'*8000),
                                       tail_text='La princesse regarde la fontaine.',tail_frames=16000)
        self.assertFalse(primary.calls)
        self.assertEqual(len(review.calls),1)

    def test_review_is_lazy_and_is_released_before_synthesis(self):
        events = []
        class Delegate:
            def __init__(self,parameters):
                self.parameters = parameters
            def synthesize(self,text,seed):
                events.append(('synth',text,seed,copy.deepcopy(self.parameters)))
                return PCM(8000,b'\1\0'*8000)
        controller = ReviewingSpeechVerifier(lambda:Reader(True),lambda:Reader(),
                                              before_review=lambda:backend.release(),progress=lambda text:None)
        backend = EvictableBackend(Delegate,{'exaggeration':1.1},
                                    before_load=controller.release_review,progress=lambda text:None)
        first = backend.synthesize('Une phrase.',123)
        controller.verify('La princesse regarde la fontaine.',first)
        self.assertIsNone(backend.delegate)
        self.assertIsNotNone(controller.review)
        backend.parameters = {'exaggeration':.6}
        second = backend.synthesize('Une phrase.',123)
        self.assertIsNone(controller.review)
        self.assertEqual(first,second)
        self.assertEqual(events[0][2],events[1][2])
        self.assertEqual(events[1][-1],{'exaggeration':.6})


class NaturalRecoveryTests(unittest.TestCase):
    def test_recovery_keeps_whole_sentences_instead_of_dangling_prepositions(self):
        first = "Ils s'endormirent et, au matin, quand le soleil se leva, on vit arriver une voiture attelée de huit chevaux blancs."
        second = "Ils avaient de blancs plumets sur la tête et leurs harnais étaient d'or."
        self.assertEqual(recovery_parts(first+' '+second),[first,second])
        self.assertEqual(recovery_parts(first[:first.index(' huit')]),[first[:first.index(' huit')]])

    def test_recovery_preserves_every_word_and_the_complete_exclamation(self):
        text = ('La princesse se mit en colère, saisit la grenouille et la projeta de toutes ses forces contre le mur : '
                '« Comme ça tu dormiras, affreuse grenouille ! »')
        parts = recovery_parts(text)
        self.assertEqual(' '.join(parts),text)
        self.assertEqual(len(parts),2)
        self.assertEqual(parts[-1],'« Comme ça tu dormiras, affreuse grenouille ! »')
        self.assertTrue(all(len(part.split())>=6 for part in parts))


if __name__ == '__main__':
    unittest.main()
