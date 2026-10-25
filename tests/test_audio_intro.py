import copy
from pathlib import Path
import tempfile
import unittest

from audio.pronunciation import pronunciation_identity, synthesis_text
from audio.voice_markup import compile_book
from audio.tts_batch import file_hash
from engine.book_engine import BookEngine
from engine.content import Content, ROOT
from tests.test_story_audio import fake_plan, runner, Verifier
from tests.test_tts_batch import FakeVoice
from tools.generate_story_audio import parser, plans_for_book


class IntroductionTests(unittest.TestCase):
    def test_intro_is_once_before_the_first_passage_in_both_modes(self):
        content = Content()
        intro = content.books['roi_grenouille']['audio_intro']['text']
        for automatic,count in ((False,21),(True,11)):
            args = parser().parse_args(['--automatic'] if automatic else [])
            args.output_dir = ROOT/'audio/experiments/roi_grenouille/files'
            plans = plans_for_book(args,content)
            self.assertEqual(len(plans),count)
            first = plans[0]
            self.assertTrue(first['text'].startswith(intro+'\n\nDans des temps'))
            self.assertEqual(first['spans'][0]['role'],'introduction')
            self.assertEqual(first['spans'][0]['emotion'],'neutral')
            self.assertTrue(all('introduction' not in [s.get('role') for s in p['spans']] for p in plans[1:]))
            engine = BookEngine(content,'roi_grenouille',automatic=automatic)
            self.assertNotIn(intro,engine.current['text'])
            self.assertEqual(first['text'],engine.current['spoken_text'])

    def test_intro_does_not_change_the_later_segment_identities(self):
        current,old = Content(),Content()
        old.books = copy.deepcopy(old.books)
        old.books['roi_grenouille'].pop('audio_intro')
        for automatic in (False,True):
            for choice in (0,1):
                new_engine = BookEngine(current,'roi_grenouille',automatic=automatic)
                old_engine = BookEngine(old,'roi_grenouille',automatic=automatic)
                self.assertNotEqual(new_engine.current['segment_id'],old_engine.current['segment_id'])
                while not new_engine.finished:
                    new_engine.choose(0 if automatic else choice)
                    old_engine.choose(0 if automatic else choice)
                    new_engine.advance()
                    old_engine.advance()
                    self.assertEqual(new_engine.current['segment_id'],old_engine.current['segment_id'])

    def test_compiler_requires_the_title_credit_and_its_exact_markup(self):
        book = copy.deepcopy(Content().books['roi_grenouille'])
        profiles = Content.read(ROOT/'audio/emotion_profiles.json')['profiles']
        del book['audio_intro']
        with self.assertRaisesRegex(ValueError,'Introduction audio obligatoire'):
            compile_book(book,profiles)
        book = copy.deepcopy(Content().books['roi_grenouille'])
        book['audio_intro']['audio_markup'] = book['audio_intro']['audio_markup'].replace('Grimm','Grimme')
        with self.assertRaisesRegex(ValueError,'modifie le texte'):
            compile_book(book,profiles)

    def test_pronunciation_is_in_the_recipe_but_asr_checks_the_original_words(self):
        text = 'Le roi-grenouille ou Henri-le-Ferré, des frères Grimm.'
        rules = [{'written':'Grimm','spoken':'Grimme'}]
        self.assertEqual(synthesis_text(text,rules),text.replace('Grimm','Grimme'))
        self.assertEqual(synthesis_text('Grimm, Grimm ! Grimmson.',rules),'Grimme, Grimme ! Grimmson.')
        class ObservingVerifier(Verifier):
            def verify(self,expected,pcm,**options):
                self_case.assertNotIn('Grimme',expected)
                return super().verify(expected,pcm,**options)
        self_case = self
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            folder = Path(folder)
            voice = FakeVoice()
            plan = fake_plan(folder,paragraphs=[text])
            plan['spans'][0]['pronunciations'] = rules
            first = runner(folder,fake=voice,verifier=ObservingVerifier())
            self.assertEqual(first.run([plan]),0)
            self.assertEqual(voice.calls[0][0],text.replace('Grimm','Grimme'))
            self.assertEqual(len(voice.calls),1)
            proof = Content.read(next((folder/'cache').glob('*/recipe.json')))
            self.assertEqual(proof['pronunciation'],pronunciation_identity(rules))
            original = file_hash(plan['output_file'])
            forbidden = lambda *args:self.fail('Aucune synthèse ni ASR après une reprise complète.')
            second = runner(folder,backend_factory=forbidden,verifier_factory=forbidden)
            self.assertEqual(second.run([plan]),0)
            self.assertEqual(file_hash(plan['output_file']),original)

    def test_changed_pronunciation_cannot_reuse_a_completed_intro(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            folder = Path(folder)
            plan = fake_plan(folder,paragraphs=['Un conte des frères Grimm.'])
            plan['spans'][0]['pronunciations'] = [{'written':'Grimm','spoken':'Grimme'}]
            self.assertEqual(runner(folder).run([plan]),0)
            original = file_hash(plan['output_file'])
            changed = copy.deepcopy(plan)
            changed['spans'][0]['pronunciations'][0]['spoken'] = 'Autre'
            with self.assertRaisesRegex(ValueError,'réglages différents'):
                runner(folder).run([changed])
            self.assertEqual(file_hash(plan['output_file']),original)

    def test_intro_reviewer_is_reloaded_after_a_tts_retry(self):
        from audio.speech_verification import compare_transcript
        class Controller(Verifier):
            def __init__(self):
                self.current,self.count = None,0
            def release(self):
                if self.current:
                    self.current.active = False
                self.current = None
            def reviewer(self):
                if self.current is None:
                    controller = self
                    class Reader:
                        active = True
                        def verify(self,expected,pcm,**options):
                            if not self.active:
                                raise ValueError('Poids du vérificateur libérés.')
                            controller.count += 1
                            actual = expected.rsplit(' ',1)[0] if controller.count == 1 else expected
                            return compare_transcript(expected,actual)
                    self.current = Reader()
                return self.current
            def verify(self,expected,pcm,**options):
                return compare_transcript(expected,expected)
        controller = Controller()
        class Voice(FakeVoice):
            def synthesize(self,text,seed):
                controller.release()
                return super().synthesize(text,seed)
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            folder = Path(folder)
            plan = fake_plan(folder,paragraphs=['Un conte des frères Grimm.'])
            plan['spans'][0]['role'] = 'introduction'
            voice = Voice()
            first = runner(folder,fake=voice,verifier=controller)
            self.assertEqual(first.run([plan]),0)
            self.assertEqual(len(voice.calls),2)
            proof = Content.read(str(plan['output_file'])+'.json')
            self.assertTrue(proof['verification']['introduction_verification']['passed'])

    def test_final_intro_rejection_retries_only_the_announcement(self):
        from audio.speech_verification import compare_transcript
        intro = 'Un conte des frères Grimm.'
        body = 'La princesse regarde la fontaine avant de parler.'
        class Controller:
            in_full,rejected = False,False
            def reviewer(self):
                return self
            def verify_complete(self,expected,pcm,**options):
                self.in_full = True
                return compare_transcript(expected,expected)
            def verify(self,expected,pcm,**options):
                if expected == intro and self.in_full and not self.rejected:
                    self.in_full,self.rejected = False,True
                    return compare_transcript(expected,expected.rsplit(' ',1)[0])
                return compare_transcript(expected,expected)
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            folder = Path(folder)
            plan = fake_plan(folder,paragraphs=[intro,body])
            plan['spans'][0]['role'] = 'introduction'
            voice = FakeVoice()
            first = runner(folder,fake=voice,verifier=Controller())
            self.assertEqual(first.run([plan]),0)
            self.assertEqual([text for text,_ in voice.calls].count(intro),2)
            self.assertEqual([text for text,_ in voice.calls].count(body),1)
            self.assertEqual(first.state['segments'][0]['span_rounds'],[1,0])

    def test_global_choice_doubt_needs_strict_head_and_physical_tail_evidence(self):
        from audio.speech_verification import compare_transcript, IncompleteSpeech
        from audio.verification_evidence import validate_evidence
        from audio.tts_batch import read_wave
        body = 'La princesse regarde la fontaine et écoute la grenouille, puis elle réfléchit longuement avant de décider comment répondre à sa demande.'
        tail = 'Que faire ? Choix 1 : Regarder la fontaine. Ou choix 2 : Répondre à la grenouille.'
        for valid_tail in (True,False,'retry'):
            with self.subTest(valid_tail=valid_tail),tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
                folder = Path(folder)
                class Controller:
                    rejections = 0
                    def reviewer(self):
                        return self
                    def verify_complete(self,expected,pcm,**options):
                        return compare_transcript(expected,expected.replace('Choix 1','Soit 1').replace('choix 2','soit 2'))
                    def verify(self,expected,pcm,**options):
                        reject = valid_tail is False or (valid_tail == 'retry' and self.rejections == 0)
                        if reject and expected == tail and options.get('vad_filter'):
                            self.rejections += 1
                            return compare_transcript(expected,expected.replace('Choix 1 :',''))
                        return compare_transcript(expected,expected)
                plan = fake_plan(folder,paragraphs=[body,tail])
                plan['spans'][-1]['role'] = 'choix'
                voice = FakeVoice()
                first = runner(folder,fake=voice,verifier=Controller())
                self.assertEqual(first.run([plan]),0 if valid_tail else 1)
                self.assertEqual([t for t,_ in voice.calls].count(body),1)
                if not valid_tail:
                    self.assertFalse(Path(plan['output_file']).exists())
                    continue
                proof = Content.read(str(plan['output_file'])+'.json')
                check = proof['verification']
                self.assertEqual(check['method'],'full-and-choices')
                pcm = read_wave(plan['output_file'])
                tail_pcm = read_wave(proof['components'][-1]['file'])
                validate_evidence(plan['text'],check,pcm,tail_text=tail,tail_pcm=tail_pcm)
                forged = copy.deepcopy(check)
                forged['tail_check']['transcript'] = tail.replace('choix 2 :','')
                with self.assertRaises(IncompleteSpeech):
                    validate_evidence(plan['text'],forged,pcm,tail_text=tail,tail_pcm=tail_pcm)


if __name__ == '__main__':
    unittest.main()
