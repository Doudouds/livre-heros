import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from audio.speech_verification import compare_transcript
from audio.tts_batch import atomic_json, atomic_wave, file_hash, PCM, read_wave, receipt_path
from audio.voice_markup import render_markup
from audio.take_history import archive_take, list_takes, read_take, take_key
from engine.audio_admin import AdminJobs, AudioInventory
from engine.content import Content, ROOT
from engine.story_import import StoryImports
from tests.test_story_audio import fake_plan, runner, Verifier
from tests.test_tts_batch import FakeVoice
from tools.generate_story_audio import parser, plans_for_book


class SeedVoice(FakeVoice):
    def synthesize(self,text,seed):
        super().synthesize(text,seed)
        return PCM(8000,(1+seed%20000).to_bytes(2,'little')*1600)


class RegenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'tmp')
        self.root = Path(self.temp.name)
        self.plan = fake_plan(self.root,paragraphs=['La princesse écoute la grenouille au bord de la fontaine.','Elle retourne au château et retrouve son père dans la salle.'])
        self.assertEqual(runner(self.root,fake=SeedVoice()).run([self.plan]),0)
        self.original = Path(self.plan['output_file']).read_bytes()
        self.proof = Content.read(receipt_path(self.plan['output_file']))

    def tearDown(self):
        self.temp.cleanup()

    def test_regeneration_uses_new_takes_archives_previous_and_resumes_same_request(self):
        voice = SeedVoice()
        fresh = runner(self.root,fake=voice,regenerate_ids={self.plan['segment_id']},regeneration_id='request-1')
        self.assertEqual(fresh.run([self.plan]),0)
        target = Path(self.plan['output_file'])
        self.assertNotEqual(target.read_bytes(),self.original)
        self.assertEqual(len(voice.calls),2)
        backups = list((self.root/'cache/previous_versions').glob('*/*.wav'))
        self.assertEqual(len(backups),2)
        self.assertIn(self.original,[p.read_bytes() for p in backups])
        current = file_hash(target)
        forbidden = lambda *args:self.fail('Une demande déjà livrée ne doit pas lancer de modèles.')
        again = runner(self.root,backend_factory=forbidden,verifier_factory=forbidden,
                       regenerate_ids={self.plan['segment_id']},regeneration_id='request-1')
        self.assertEqual(again.run([self.plan]),0)
        self.assertEqual(file_hash(target),current)
        self.assertTrue(again.state['segments'][0]['reused'])

    def test_failed_new_take_keeps_current_audio_and_receipt_ready(self):
        class Refuse(Verifier):
            def verify(self,expected,pcm,**kwargs):
                return compare_transcript(expected,'Des paroles complètement différentes et incomplètes.')
        fresh = runner(self.root,fake=SeedVoice(),verifier=Refuse(),attempts=1,
                       regenerate_ids={self.plan['segment_id']},regeneration_id='request-fail')
        self.assertEqual(fresh.run([self.plan]),1)
        self.assertEqual(Path(self.plan['output_file']).read_bytes(),self.original)
        self.assertEqual(Content.read(receipt_path(self.plan['output_file'])),self.proof)

    def test_interrupted_request_keeps_completed_take_and_old_audio(self):
        voice = SeedVoice(crash_on=2)
        fresh = runner(self.root,fake=voice,regenerate_ids={self.plan['segment_id']},regeneration_id='request-crash')
        with self.assertRaises(KeyboardInterrupt):
            fresh.run([self.plan])
        self.assertEqual(Path(self.plan['output_file']).read_bytes(),self.original)
        voice = SeedVoice()
        resumed = runner(self.root,fake=voice,regenerate_ids={self.plan['segment_id']},regeneration_id='request-crash')
        self.assertEqual(resumed.run([self.plan]),0)
        self.assertEqual(len(voice.calls),1)
        self.assertEqual(voice.calls[0][0],self.plan['spans'][1]['text'])

    def test_exact_variant_selection_does_not_fall_back_to_another_choice(self):
        args = parser().parse_args([])
        args.output_dir = ROOT/'audio/experiments/roi_grenouille/files'
        full = plans_for_book(args)
        args.segment_id = full[6]['segment_id']
        self.assertEqual(plans_for_book(args),[full[6]])
        args.automatic = True
        with self.assertRaisesRegex(ValueError,'inconnue'):
            plans_for_book(args)

    def test_partial_take_only_synthesizes_selected_portion_and_preserves_other_pcm(self):
        voice = SeedVoice()
        fresh = runner(self.root,fake=voice,regenerate_ids={self.plan['segment_id']},
                       regeneration_id='partial-1',regenerate_spans={1})
        self.assertEqual(fresh.run([self.plan]),0)
        self.assertEqual([call[0] for call in voice.calls],[self.plan['spans'][1]['text']])
        proof = Content.read(receipt_path(self.plan['output_file']))
        self.assertEqual(proof['components'][0],self.proof['components'][0])
        self.assertNotEqual(proof['components'][1]['sha256'],self.proof['components'][1]['sha256'])
        self.assertEqual(proof['span_rounds'],[0,1])
        self.assertEqual(proof['regenerated_spans'],[1])
        pcm = read_wave(self.plan['output_file'])
        self.assertEqual(pcm.frames[:pcm.sample_rate*2],b'\0'*(pcm.sample_rate*2))
        self.assertTrue(proof['verification']['passed'])

    def test_partial_resume_keeps_new_portions_and_the_unselected_original(self):
        plan = fake_plan(self.root,number=2,paragraphs=[s['text'] for s in self.plan['spans']]+
                         ['Le roi attendait sa fille dans la grande salle du château.'])
        self.assertEqual(runner(self.root,fake=SeedVoice()).run([plan]),0)
        before = Path(plan['output_file']).read_bytes()
        old = Content.read(receipt_path(plan['output_file']))
        options = dict(regenerate_ids={plan['segment_id']},regeneration_id='partial-crash',regenerate_spans={0,2})
        with self.assertRaises(KeyboardInterrupt):
            runner(self.root,fake=SeedVoice(crash_on=2),**options).run([plan])
        self.assertEqual(Path(plan['output_file']).read_bytes(),before)
        voice = SeedVoice()
        self.assertEqual(runner(self.root,fake=voice,**options).run([plan]),0)
        self.assertEqual([c[0] for c in voice.calls],[plan['spans'][2]['text']])
        current = Content.read(receipt_path(plan['output_file']))
        self.assertEqual(current['components'][1],old['components'][1])
        forbidden = lambda *args:self.fail('Cette demande a déjà été livrée.')
        self.assertEqual(runner(self.root,backend_factory=forbidden,verifier_factory=forbidden,**options).run([plan]),0)

    def test_partial_publish_crash_recovers_using_pinned_source_and_cached_takes(self):
        options = dict(regenerate_ids={self.plan['segment_id']},regeneration_id='partial-publication',regenerate_spans={1})
        with patch('audio.styled_generation.write_receipt',side_effect=KeyboardInterrupt),self.assertRaises(KeyboardInterrupt):
            runner(self.root,fake=SeedVoice(),**options).run([self.plan])
        voice = SeedVoice()
        self.assertEqual(runner(self.root,fake=voice,**options).run([self.plan]),0)
        self.assertEqual(voice.calls,[])
        current = Content.read(receipt_path(self.plan['output_file']))
        self.assertEqual(current['components'][0],self.proof['components'][0])

    def test_restore_verifies_without_tts_then_partial_take_preserves_restored_source(self):
        old_key = take_key(self.proof)
        self.assertEqual(runner(self.root,fake=SeedVoice(),regenerate_ids={self.plan['segment_id']},regeneration_id='full-1').run([self.plan]),0)
        class CountFull(Verifier):
            full_checks = 0
            def verify(self,expected,pcm,**options):
                if options.get('vad_filter'):
                    self.full_checks += 1
                return super().verify(expected,pcm,**options)
        verifier = CountFull()
        forbidden = lambda *args:self.fail('Restaurer ne doit pas lancer Chatterbox.')
        self.assertEqual(runner(self.root,backend_factory=forbidden,verifier=verifier,restore_take=old_key).run([self.plan]),0)
        self.assertGreater(verifier.full_checks,0)
        self.assertEqual(Path(self.plan['output_file']).read_bytes(),self.original)
        voice = SeedVoice()
        self.assertEqual(runner(self.root,fake=voice,regenerate_ids={self.plan['segment_id']},
                               regeneration_id='partial-restored',regenerate_spans={1}).run([self.plan]),0)
        self.assertEqual(len(voice.calls),1)
        self.assertEqual(Content.read(receipt_path(self.plan['output_file']))['components'][0],self.proof['components'][0])

    def test_history_keeps_ten_versions_and_never_deletes_shared_components(self):
        for number in range(12):
            self.assertEqual(runner(self.root,fake=SeedVoice(),regenerate_ids={self.plan['segment_id']},
                                    regeneration_id='take-'+str(number)).run([self.plan]),0)
        identity = self.proof['identity']
        history = list_takes(self.root/'cache',self.plan['output_file'],identity)
        self.assertEqual(len(history),10)
        self.assertTrue(history[0]['current'])
        self.assertEqual(len(list((self.root/'cache/previous_versions'/identity).glob('*.wav'))),10)
        self.assertTrue(Path(self.proof['components'][0]['file']).is_file())
        with self.assertRaises(FileNotFoundError):
            read_take(self.root/'cache',identity,take_key(self.proof))
        self.assertEqual(runner(self.root,restore_take=history[-1]['key']).run([self.plan]),0)
        self.assertEqual(len(list_takes(self.root/'cache',self.plan['output_file'],identity)),10)

    def test_failed_restore_keeps_current_wav_and_receipt_and_partial_never_repairs_unselected(self):
        self.assertEqual(runner(self.root,fake=SeedVoice(),regenerate_ids={self.plan['segment_id']},regeneration_id='new').run([self.plan]),0)
        before = Path(self.plan['output_file']).read_bytes()
        proof = Content.read(receipt_path(self.plan['output_file']))
        self.assertEqual(runner(self.root,verifier=Verifier(fail_full=1),restore_take=take_key(self.proof)).run([self.plan]),1)
        self.assertEqual(Path(self.plan['output_file']).read_bytes(),before)
        self.assertEqual(Content.read(receipt_path(self.plan['output_file'])),proof)
        class RejectOther(Verifier):
            def verify(self,expected,pcm,**options):
                if options.get('vad_filter') and expected==self_text:
                    from audio.speech_verification import IncompleteSpeech
                    raise IncompleteSpeech(dict(passed=False,reasons=['Refus de la première portion.'],affected_spans=[0]))
                return super().verify(expected,pcm,**options)
        self_text = self.plan['text']
        voice = SeedVoice()
        self.assertEqual(runner(self.root,fake=voice,verifier=RejectOther(),regenerate_ids={self.plan['segment_id']},
                               regeneration_id='outside',regenerate_spans={1}).run([self.plan]),1)
        self.assertEqual([c[0] for c in voice.calls],[self.plan['spans'][1]['text']])
        self.assertEqual(Path(self.plan['output_file']).read_bytes(),before)

    def test_missing_unselected_component_refuses_partial_without_synthesis(self):
        Path(self.proof['components'][0]['file']).unlink()
        forbidden = lambda *args:self.fail('Un composant absent ne doit pas faire refaire le reste.')
        self.assertEqual(runner(self.root,backend_factory=forbidden,regenerate_ids={self.plan['segment_id']},
                               regeneration_id='missing',regenerate_spans={1}).run([self.plan]),1)
        self.assertEqual(Path(self.plan['output_file']).read_bytes(),self.original)
        self.assertEqual(Content.read(receipt_path(self.plan['output_file'])),self.proof)

    def test_legacy_history_is_deduplicated_and_corrupt_take_is_not_restored(self):
        from audio.take_history import history_directory
        directory = history_directory(self.root/'cache',self.proof['identity'])
        legacy = directory/(self.proof['sha256']+'.wav')
        shutil.copyfile(self.plan['output_file'],legacy)
        atomic_json(receipt_path(legacy),self.proof)
        self.assertEqual(len(list_takes(self.root/'cache',self.plan['output_file'],self.proof['identity'])),1)
        self.assertEqual(runner(self.root,fake=SeedVoice(),regenerate_ids={self.plan['segment_id']},regeneration_id='legacy-new').run([self.plan]),0)
        history = list_takes(self.root/'cache',self.plan['output_file'],self.proof['identity'])
        self.assertEqual(len(history),2)
        self.assertEqual(len(list(directory.glob('*.wav'))),2)
        before = Path(self.plan['output_file']).read_bytes()
        with Path(history[1]['file']).open('ab') as stream:
            stream.write(b'corruption')
        self.assertEqual(len(list_takes(self.root/'cache',self.plan['output_file'],self.proof['identity'])),1)
        self.assertEqual(runner(self.root,restore_take=history[1]['key']).run([self.plan]),1)
        self.assertEqual(Path(self.plan['output_file']).read_bytes(),before)


def import_response(texts):
    return dict(segments=[dict(title='Passage '+str(i+1),text=text,
                  audio_markup=render_markup(text,[dict(text=text,emotion='neutral')]),
                  choice_question='Que doit faire la jeune fille ?' if i<len(texts)-1 else '',
                  choices=[dict(text='Regarder le chemin',consequence='Elle regarda le chemin.',
                                consequence_audio_markup='<voix emotion="neutral">Elle regarda le chemin.</voix>'),
                           dict(text='Écouter le vent',consequence='Elle écouta le vent.',
                                consequence_audio_markup='<voix emotion="tendresse">Elle écouta le vent.</voix>')]
                         if i<len(texts)-1 else []) for i,text in enumerate(texts)])


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'tmp')
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT/'content',self.root/'content')
        (self.root/'audio').mkdir()
        shutil.copyfile(ROOT/'audio/emotion_profiles.json',self.root/'audio/emotion_profiles.json')
        shutil.copyfile(ROOT/'config.json',self.root/'config.json')
        (self.root/'chatterbox').mkdir()
        atomic_wave(self.root/'chatterbox/Recording.wav',PCM(8000,b'\1\0'*24000))
        self.service = StoryImports(self.root)
        self.texts = ['Une jeune fille traversait la forêt et suivait le chemin près de sa maison.',
                      'Elle rentra chez elle et retrouva sa famille.']
        self.draft = self.service.create('Un conte de test','Les frères Grimm','\n\n'.join(self.texts))
        self.folder = self.service.draft(self.draft)
        atomic_json(self.folder/'candidate.json',import_response(self.texts))

    def tearDown(self):
        self.temp.cleanup()

    def test_validation_and_explicit_integration_preserve_source_and_two_modes(self):
        book = self.service.validate(self.draft)
        self.assertEqual(book['audio_intro']['author_credit'],'des frères Grimm')
        self.assertTrue(book['admin_preview_required'])
        self.assertEqual([s['text'] for s in book['scenes']],self.texts)
        self.assertFalse((self.root/'content/books'/(self.draft+'.json')).exists())
        request = Content.read(self.folder/'request.json')
        request['status'] = 'prepared'
        atomic_json(self.folder/'request.json',request)
        self.service.publish(self.draft)
        content = Content(self.root)
        args = parser().parse_args(['--book',self.draft])
        args.output_dir = self.root/content.config['book_audio_roots'][self.draft]
        self.assertEqual(len(plans_for_book(args,content)),3)
        args.automatic = True
        self.assertEqual(len(plans_for_book(args,content)),2)
        self.assertFalse(AudioInventory(self.root).preview_approved(self.draft))
        with self.assertRaisesRegex(ValueError,'premiers audios'):
            AdminJobs(self.root).start_audio(self.draft,both=True)
        with self.assertRaises(ValueError):
            self.service.publish(self.draft)

    def test_preview_approval_requires_both_verified_files_and_detects_changed_reference(self):
        request = Content.read(self.folder/'request.json'); request['status']='prepared'
        atomic_json(self.folder/'request.json',request)
        self.service.publish(self.draft)
        inventory = AudioInventory(self.root)
        with self.assertRaises(ValueError):
            inventory.approve_previews(self.draft)
        class TaggedVerifier(Verifier):
            def verify(self,expected,pcm,**options):
                value = super().verify(expected,pcm,**options)
                value.update(review_verifier='Whisper Medium',final_review_required=True)
                return value
            def verify_complete(self,expected,pcm,**options):
                return self.verify(expected,pcm,vad_filter=True)
        content = Content(self.root)
        for automatic in (False,True):
            args = parser().parse_args(['--book',self.draft,'--segment','1']+(['--automatic'] if automatic else []))
            args.output_dir = self.root/content.config['book_audio_roots'][self.draft]
            plan = plans_for_book(args,content)[0]
            process = runner(self.root,verifier=TaggedVerifier(),output_dir=args.output_dir,
                             voice_sha=file_hash(self.root/'chatterbox/Recording.wav'))
            self.assertEqual(process.run([plan]),0)
        inventory.approve_previews(self.draft)
        self.assertTrue(inventory.preview_approved(self.draft))
        wave = self.root/'chatterbox/Recording.wav'
        atomic_wave(wave,PCM(8000,b'\2\0'*24000))
        self.assertFalse(inventory.preview_approved(self.draft))
        self.assertEqual(inventory.rows(self.draft)[0]['status'],'invalid')

    def test_missing_source_bad_tone_or_choice_cannot_enter_library(self):
        for mode in ('missing_text','bad_tone','missing_choice'):
            value = import_response(self.texts)
            if mode=='missing_text':
                value['segments'][1]['text'] = 'Une fin inventée.'
            elif mode=='bad_tone':
                value['segments'][0]['audio_markup'] = value['segments'][0]['audio_markup'].replace('neutral','inconnue')
            else:
                value['segments'][0]['choices'].pop()
            atomic_json(self.folder/'candidate.json',value)
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                self.service.validate(self.draft)
        self.assertFalse((self.root/'content/books'/(self.draft+'.json')).exists())

    def test_codex_uses_read_only_structured_output_and_stdin_without_shell_interpolation(self):
        class Jobs:
            def start(self,label,intent,specs,finish):
                self.spec = specs(self_folder)[0]
                self.finish = finish
                return {'status':'running'}
        self_folder = self.root/'jobs'
        jobs = Jobs()
        with patch('engine.story_import.codex_executable',return_value='C:/Program Files/Codex/codex.exe'):
            self.service.prepare(jobs,self.draft)
        command = jobs.spec['command']
        self.assertIn('read-only',command)
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',command)
        self.assertEqual(command[-1],'-')
        self.assertNotIn('Un conte de test',command)
        self.assertTrue(Path(jobs.spec['stdin']).is_file())
        atomic_json(self.folder/'candidate.json',import_response(self.texts))
        jobs.finish()
        self.assertEqual(Content.read(self.folder/'request.json')['status'],'prepared')
        self.assertFalse((self.root/'content/books'/(self.draft+'.json')).exists())

    def test_publish_failure_rolls_back_new_book_without_changing_config(self):
        request = Content.read(self.folder/'request.json'); request['status']='prepared'
        atomic_json(self.folder/'request.json',request)
        original = (self.root/'config.json').read_bytes()
        from engine.story_import import atomic_json as real_atomic
        def fail_config(path,value):
            if Path(path)==self.root/'config.json':
                raise OSError('Écriture interrompue')
            return real_atomic(path,value)
        with patch('engine.story_import.atomic_json',side_effect=fail_config),self.assertRaises(OSError):
            self.service.publish(self.draft)
        self.assertEqual((self.root/'config.json').read_bytes(),original)
        self.assertFalse((self.root/'content/books'/(self.draft+'.json')).exists())
        self.assertFalse((self.root/f'content/authored/books/{self.draft}_source.txt').exists())

    def test_codex_process_contract_prepares_a_draft_without_publishing(self):
        response = json.dumps(import_response(self.texts),ensure_ascii=False)
        script = ('import sys,json; from pathlib import Path; args=sys.argv; prompt=sys.stdin.read(); '
                  'assert "lecture seule" in prompt; '
                  'target=Path(args[args.index("--output-last-message")+1]); '
                  f'target.write_text({response!r},encoding="utf-8"); '
                  'print(json.dumps({"type":"item.completed","item":{"text":"Brouillon prêt à relire."}},ensure_ascii=False))')
        def fake_codex(command,**options):
            return subprocess.Popen([sys.executable,'-c',script,*command[1:]],**options)
        jobs = AdminJobs(self.root,popen=fake_codex)
        with patch('engine.story_import.codex_executable',return_value='fake-codex'):
            self.service.prepare(jobs,self.draft)
        jobs.thread.join(timeout=15)
        self.assertFalse(jobs.busy)
        self.assertEqual(jobs.snapshot()['status'],'succeeded',jobs.snapshot().get('error'))
        self.assertIn('Brouillon prêt à relire',jobs.log_tail())
        self.assertEqual(Content.read(self.folder/'request.json')['status'],'prepared')
        self.assertFalse((self.root/'content/books'/(self.draft+'.json')).exists())


class JobTests(unittest.TestCase):
    def test_partial_job_builds_exact_portion_command_and_rejects_invalid_selection(self):
        inventory = AudioInventory()
        row = inventory.rows('roi_grenouille')[0]
        jobs = AdminJobs()
        with patch.object(jobs,'start') as start:
            jobs.start_audio('roi_grenouille',segment_id=row['plan']['segment_id'],regenerate=True,spans=[4,2,2])
            label,intent,specs = start.call_args.args
            command = specs(ROOT/'reports/admin/fake-job')[0]['command']
            self.assertEqual(intent['spans'],[2,4])
            self.assertEqual(command[-6:-2],['--span','2','--span','4'])
            self.assertIn(row['plan']['segment_id'],command)
        for spans in ([],[0],[999]):
            with self.subTest(spans=spans),self.assertRaises(ValueError):
                jobs.start_audio('roi_grenouille',segment_id=row['plan']['segment_id'],regenerate=True,spans=spans)

    def test_background_job_lock_log_and_release_after_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            root = Path(temp)
            jobs = AdminJobs(root)
            def specs(folder):
                return [dict(command=[sys.executable,'-c','import time; print("Début",flush=True); time.sleep(.3); raise SystemExit(2)'])]
            jobs.start('Essai',{'kind':'test'},specs)
            other = AdminJobs(root)
            with self.assertRaises(RuntimeError):
                other.start('Autre',{},specs)
            jobs.thread.join(timeout=10)
            self.assertFalse(jobs.busy)
            self.assertEqual(jobs.snapshot()['status'],'failed')
            self.assertIn('Début',jobs.log_tail())
            other.start('Suite',{},lambda folder:[dict(command=[sys.executable,'-c','print("OK")'])])
            other.thread.join(timeout=10)
            self.assertEqual(other.snapshot()['status'],'succeeded')

    def test_resume_retains_the_exact_variant_mode_and_request_token(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            root = Path(temp)
            intent = dict(kind='audio',book_id='roi_grenouille',automatic=True,segment_id='exact-variant',
                          regenerate=True,both=False,first=False,regeneration_id='same-request',spans=[2,4])
            atomic_json(root/'reports/admin/last_job.json',dict(status='stopped',intent=intent))
            jobs = AdminJobs(root)
            with patch.object(jobs,'start_audio') as start:
                jobs.resume()
                self.assertEqual(start.call_args.kwargs,{k:v for k,v in intent.items() if k!='kind'})

    def test_stop_terminates_its_owned_process_and_releases_the_job_lock(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temp:
            root = Path(temp)
            jobs = AdminJobs(root)
            jobs.start('Attente',{},lambda folder:[dict(command=[sys.executable,'-c','import time; time.sleep(20)'])])
            deadline = time.monotonic()+3
            while jobs.process is None and jobs.busy and time.monotonic()<deadline:
                threading.Event().wait(.01)
            jobs.stop()
            jobs.thread.join(timeout=5)
            try:
                self.assertFalse(jobs.busy)
                self.assertEqual(jobs.snapshot()['status'],'stopped')
            finally:
                if jobs.busy and jobs.process is not None:
                    jobs.process.terminate()
                    jobs.thread.join(timeout=5)


class AdminUITests(unittest.TestCase):
    def test_panel_opens_without_tts_displays_two_modes_and_routes_exact_selection(self):
        import tkinter as tk
        from ui.pc_ui import PcUI
        root = tk.Tk(); root.withdraw()
        app = None
        try:
            with patch.dict('sys.modules',{'torch':None,'chatterbox':None}):
                app = PcUI(root,Content())
                app.open_admin()
                panel = app.admin_window
                panel.window.withdraw()
                root.update()
                self.assertEqual(len(panel.tree.get_children()),21)
                self.assertTrue(all(r['status']=='ready' for r in panel.rows_by_id.values()))
                selected = panel.tree.get_children()[6]
                panel.tree.selection_set(selected); root.update()
                with patch.object(panel.jobs,'start_audio') as start:
                    panel.regenerate_button.invoke()
                    self.assertEqual(start.call_args.kwargs['segment_id'],selected)
                    self.assertTrue(start.call_args.kwargs['regenerate'])
                    panel.portion_tree.selection_set('2'); root.update()
                    panel.regenerate_portions_button.invoke()
                    self.assertEqual(start.call_args.kwargs['spans'],[2])
                    self.assertEqual(start.call_args.kwargs['segment_id'],selected)
                    self.assertIn(panel.selected()['plan']['spans'][1]['text'],panel.portion_text.get('1.0','end'))
                self.assertEqual(len(panel.history_tree.get_children()),1)
                self.assertEqual(str(panel.restore_button['state']),'disabled')
                panel.mode.set('Écoute automatique'); panel.refresh_rows()
                self.assertEqual(len(panel.tree.get_children()),11)
                original = panel
                app.open_admin()
                self.assertIs(app.admin_window,original)
                panel.close()
                self.assertIsNone(app.admin_window)
        finally:
            if app is not None:
                app.close()
            elif root.winfo_exists():
                root.destroy()


if __name__ == '__main__':
    unittest.main()
