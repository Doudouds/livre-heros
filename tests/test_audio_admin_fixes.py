import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, PropertyMock

from audio.audio_player import LocalAudioPlayer, wave_with_lead_in
from audio.speech_verification import compare_transcript, IncompleteSpeech
from audio.take_history import take_key
from audio.tts_batch import atomic_json, file_hash, read_wave, receipt_path
from audio.verification_evidence import validate_evidence
from engine.audio_admin import AdminJobs
from engine.content import Content, ROOT
from tests import test_audio_admin as fixtures
from tests.test_audio_admin import SeedVoice
from tests.test_story_audio import fake_plan, runner, Verifier
from tests.test_pc_audio_tts import FakeWindowsWave, write_test_wav


class ToneTests(unittest.TestCase):
    setUp = fixtures.RegenerationTests.setUp
    tearDown = fixtures.RegenerationTests.tearDown
    def test_tone_is_applied_only_to_selection_traced_and_preserved_on_next_take(self):
        palette = dict(neutral=self.plan['spans'][0]['parameters'],joie=dict(exaggeration=1.4,cfg_weight=.2))
        class Voice(SeedVoice):
            parameters_seen = []
            def synthesize(self,text,seed):
                self.parameters_seen.append(copy.deepcopy(self.parameters))
                return super().synthesize(text,seed)
        voice = Voice()
        options = dict(palette=palette,regenerate_ids={self.plan['segment_id']},regenerate_spans={1})
        self.assertEqual(runner(self.root,fake=voice,emotion='joie',regeneration_id='joy',**options).run([self.plan]),0)
        proof = Content.read(receipt_path(self.plan['output_file']))
        self.assertEqual(proof['tone_overrides'],{'1':'joie'})
        self.assertEqual(proof['components'][0],self.proof['components'][0])
        self.assertEqual(proof['components'][1]['parameters'],palette['joie'])
        self.assertEqual(voice.parameters_seen,[palette['joie']])
        self.assertEqual(proof['profile'],self.proof['profile'])
        # Reprendre l'autre portion ne doit pas perdre le ton choisi.
        options['regenerate_spans'] = {0}
        self.assertEqual(runner(self.root,fake=SeedVoice(),regeneration_id='other',**options).run([self.plan]),0)
        after = Content.read(receipt_path(self.plan['output_file']))
        self.assertEqual(after['components'][1],proof['components'][1])
        self.assertEqual(after['tone_overrides'],{'1':'joie'})
        self.assertEqual(runner(self.root,palette=palette,restore_take=take_key(self.proof)).run([self.plan]),0)
        self.assertFalse(Content.read(receipt_path(self.plan['output_file']))['tone_overrides'])
        self.assertEqual(Path(self.plan['output_file']).read_bytes(),self.original)

    def test_invalid_tone_is_refused_before_synthesis(self):
        forbidden = lambda *args:self.fail('Ton inconnu envoyé à Chatterbox.')
        with self.assertRaises(ValueError):
            runner(self.root,backend_factory=forbidden,emotion='inconnue',palette={},
                   regenerate_ids={self.plan['segment_id']},regenerate_spans={1}).run([self.plan])
        self.assertEqual(Path(self.plan['output_file']).read_bytes(),self.original)

    def test_report_exposes_active_portion_before_tts_and_global_verification(self):
        test = self
        class Voice(SeedVoice):
            def synthesize(self,text,seed):
                record = Content.read(test.root/'status.json')['segments'][0]
                test.assertEqual(record['active_portion'],1)
                test.assertEqual(record['spans'][1]['status'],'generating')
                return super().synthesize(text,seed)
        class Check(Verifier):
            def verify(self,expected,pcm,**options):
                if options.get('vad_filter') and expected==test.plan['text']:
                    record = Content.read(test.root/'status.json')['segments'][0]
                    test.assertEqual(record['stage'],'verification')
                    test.assertEqual(record['spans'][1]['status'],'checking')
                return super().verify(expected,pcm,**options)
        self.assertEqual(runner(self.root,fake=Voice(),verifier=Check(),regenerate_ids={self.plan['segment_id']},
                               regenerate_spans={1},regeneration_id='progress').run([self.plan]),0)


class HeadEvidenceTests(unittest.TestCase):
    def test_head_tail_doubt_is_checked_on_actual_narrative_tail_without_changing_audio(self):
        first = ' '.join(['La princesse regardait la fontaine avant de parler à la grenouille.']*4)
        last = 'Elle aperçut alors une grenouille qui tendait sa tête hors de l’eau.'
        choices = 'Que faire ? Choix 1 : Regarder la fontaine. Ou choix 2 : Répondre à la grenouille.'
        head = first+' '+last
        for correct_tail in (True,False):
            with self.subTest(correct_tail=correct_tail),tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
                folder = Path(folder)
                class Check(Verifier):
                    def reviewer(self): return self
                    def verify_complete(self,expected,pcm,**options):
                        return compare_transcript(expected,expected.replace('Choix 1','Soit 1').replace('choix 2','soit 2'))
                    def verify(self,expected,pcm,**options):
                        if options.get('vad_filter') and expected==head:
                            return compare_transcript(expected,expected+' Merci pour cette vidéo.')
                        if options.get('vad_filter') and expected==last and not correct_tail:
                            return compare_transcript(expected,expected.rsplit(' ',3)[0])
                        result=compare_transcript(expected,expected)
                        result['review_verifier']='Whisper Medium'
                        return result
                plan=fake_plan(folder,paragraphs=[first,last,choices])
                plan['spans'][-1]['role']='choix'
                run=runner(folder,fake=SeedVoice(),verifier=Check(),attempts=1)
                self.assertEqual(run.run([plan]),0 if correct_tail else 1)
                if not correct_tail:
                    self.assertFalse(Path(plan['output_file']).exists())
                    continue
                proof=Content.read(receipt_path(plan['output_file']))
                self.assertEqual(proof['verification']['head_check']['method'],'full-and-tail')
                pcm=read_wave(plan['output_file']);tail=read_wave(proof['components'][-1]['file'])
                validate_evidence(plan['text'],proof['verification'],pcm,tail_text=choices,tail_pcm=tail)
                forged=copy.deepcopy(proof['verification']);forged['head_tail_frames']-=2
                with self.assertRaises(ValueError):
                    validate_evidence(plan['text'],forged,pcm,tail_text=choices,tail_pcm=tail)


class WindowsAndJobTests(unittest.TestCase):
    def test_long_component_uses_short_playback_copy_and_preserves_samples(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            root=Path(folder);source=root/('a'*64)/'components'/('b'*64+'.wav')
            frames=write_test_wav(source)
            original=file_hash(source)
            player=LocalAudioPlayer(root,lead_in_ms=0)
            backend=FakeWindowsWave()
            with patch('audio.audio_player.sys.platform','win32'),patch('audio.audio_player.WindowsWavePlayer',return_value=backend):
                self.assertTrue(player.play('missing',str(source)))
                actual=backend.calls[0][1]
                self.assertNotEqual(actual,source)
                self.assertLess(len(str(actual)),len(str(source)))
                self.assertEqual(read_wave(actual).frames,frames)
                self.assertEqual(file_hash(source),original)
                player.stop()

    def test_zero_exit_code_cannot_hide_failed_audio_report_or_legacy_false_success(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            root=Path(folder);report=root/'report.json'
            atomic_json(report,dict(status='failed',segments=[dict(status='failed',error='Contrôle final refusé.')]))
            jobs=AdminJobs(root)
            specs=lambda folder:[dict(command=[sys.executable,'-c','pass'],report=str(report))]
            jobs.start('Essai',dict(kind='audio'),specs)
            jobs.thread.join(10)
            self.assertEqual(jobs.snapshot()['status'],'failed')
            self.assertIn('Contrôle final refusé',jobs.snapshot()['error'])
            jobs.current['status']='succeeded'
            self.assertEqual(jobs.snapshot()['status'],'failed')

    def test_launcher_returns_real_child_failure_before_models_are_loaded(self):
        if not (ROOT/'.venv-tts/Scripts/python.exe').is_file():
            self.skipTest('Environnement local absent.')
        result=subprocess.run([sys.executable,str(ROOT/'generer_audio_conte.py'),'--book','codex_inexistant_test'],
                              cwd=ROOT,capture_output=True,timeout=30)
        self.assertEqual(result.returncode,1)


class PortionUITests(unittest.TestCase):
    def test_dropdown_routes_emotion_and_busy_or_failed_portion_is_visible(self):
        import tkinter as tk
        from ui.pc_ui import PcUI
        root=tk.Tk();root.withdraw();app=None
        try:
            app=PcUI(root,Content());app.open_admin();panel=app.admin_window
            panel.window.withdraw();root.update()
            panel.portion_tree.selection_set('2');root.update()
            panel.tone.set('Joie')
            with patch.object(panel.jobs,'start_audio') as start:
                panel.regenerate_portions_button.invoke()
                self.assertEqual(start.call_args.kwargs['emotion'],'joie')
            record=dict(status='generating',spans=[dict(status='kept'),dict(status='generating')])
            intent=dict(spans=[2])
            with patch.object(panel.jobs,'audio_record',return_value=(record,intent)),patch.object(type(panel.jobs),'busy',new_callable=PropertyMock,return_value=True):
                panel.refresh_portion_states(panel.selected())
                self.assertIn('⌛',panel.portion_tree.set('2','number'))
                self.assertIn('generating',panel.portion_tree.item('2','tags'))
            record.update(status='failed',error='Contrôle de narration refusé.')
            record['spans'][1]['status']='assembly_failed'
            with patch.object(panel.jobs,'audio_record',return_value=(record,intent)):
                panel.refresh_portion_states(panel.selected())
                self.assertIn('⚠',panel.portion_tree.set('2','number'))
                self.assertIn('en service',panel.portion_status.get())
        finally:
            if app: app.close()
            elif root.winfo_exists(): root.destroy()


if __name__=='__main__': unittest.main()
