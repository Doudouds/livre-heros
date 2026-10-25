import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from audio.tts_batch import PCM, atomic_wave
from engine.book_engine import BookEngine
from engine.content import Content, ROOT
from tests.test_pc_audio_tts import FakeWindowsWave
from tests.test_story_audio import runner
from tools.generate_faithful_audio import assemble
from tools.generate_story_audio import main, parser, plans_for_book


class AutomaticEngineTests(unittest.TestCase):
    def test_auto_text_is_exactly_the_choice_one_route_without_questions(self):
        content = Content()
        automatic = BookEngine(content,'roi_grenouille',automatic=True)
        interactive = BookEngine(content,'roi_grenouille')
        passages = 0
        while True:
            a,i = automatic.current,interactive.current
            self.assertEqual(a['text'],i['text'])
            self.assertEqual(a['spoken_text'],i['text'])
            self.assertIsNone(a['choice_prompt'])
            self.assertIn('_automatic_',a['segment_id'])
            self.assertNotEqual(a['segment_id'],i['segment_id'])
            self.assertNotIn('Choix 1 :',a['spoken_text'])
            self.assertNotIn('Que doit faire',a['spoken_text'])
            passages += 1
            if automatic.finished:
                break
            with self.assertRaises(ValueError):
                automatic.choose(1)
            automatic.choose(0)
            interactive.choose(0)
            automatic.advance()
            interactive.advance()
        self.assertEqual(passages,11)
        self.assertEqual([c['choice_index'] for c in automatic.journal['choices']],[0]*10)
        self.assertGreater(interactive.state.estimated_seconds,automatic.state.estimated_seconds)

    def test_automatic_journal_replays_in_automatic_mode(self):
        content = Content()
        engine = BookEngine(content,'roi_grenouille',automatic=True)
        for _ in range(4):
            engine.choose(0)
            engine.advance()
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            path = Path(folder)/'session.json'
            engine.export_session(path)
            replay = BookEngine.replay(content,path)
        self.assertTrue(replay.automatic)
        self.assertEqual(replay.current,engine.current)
        self.assertEqual(replay.journal,engine.journal)

    def test_auto_generation_has_eleven_files_and_shares_narrative_takes(self):
        args = parser().parse_args(['--automatic','--dry-run'])
        args.output_dir = ROOT/'audio/experiments/roi_grenouille/files'
        plans = plans_for_book(args)
        regular = copy.copy(args)
        regular.automatic = False
        interactive = plans_for_book(regular)
        self.assertEqual(len(plans),11)
        self.assertEqual(len(interactive),21)
        self.assertEqual(plans[0]['spans'],interactive[0]['spans'][:-1])
        self.assertTrue(all(s.get('role') != 'choix' for p in plans for s in p['spans']))
        self.assertTrue(all('Choix 1 :' not in p['text'] for p in plans))
        engine = BookEngine(Content(),'roi_grenouille',automatic=True)
        for plan in plans:
            self.assertEqual(plan['segment_id'],engine.current['segment_id'])
            self.assertEqual(plan['text'],engine.current['spoken_text'])
            if not engine.finished:
                engine.choose(0)
                engine.advance()
        args.choice = 2
        with self.assertRaisesRegex(ValueError,'incompatible'):
            plans_for_book(args)

    def test_auto_dry_run_and_generation_keep_checks_enabled(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            directory = Path(folder)
            with patch.dict('sys.modules',{'torch':None,'chatterbox':None}),patch('builtins.print'):
                self.assertEqual(main(['--automatic','--dry-run','--output-dir',str(directory/'files'),
                                       '--report',str(directory/'status.json')]),0)
            plans = json.loads((directory/'audio_plan.json').read_text(encoding='utf-8'))['segments']
            self.assertEqual(len(plans),11)
            run = runner(directory)
            self.assertEqual(run.run(plans[:1]),0)
            proof = run.state['segments'][0]
            self.assertTrue(proof['verification']['passed'])
            self.assertTrue(proof['verification']['choices_matched'])
            self.assertNotIn('Choix 1',proof['verification']['transcript'])


class AutomaticUITests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.directory = tempfile.TemporaryDirectory(dir=ROOT/'tmp')
        self.folder = Path(self.directory.name)
        self.content = Content()
        self.content.config = copy.deepcopy(self.content.config)
        self.content.config['audio_root'] = (self.folder/'legacy').relative_to(ROOT).as_posix()
        self.content.config['book_audio_roots']['roi_grenouille'] = (self.folder/'files').relative_to(ROOT).as_posix()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.attributes('-alpha',0)
        self.backend = FakeWindowsWave()
        self.patch_backend = patch('audio.audio_player.WindowsWavePlayer',return_value=self.backend)
        self.patch_backend.start()
        self.patch_info = patch('ui.pc_ui.messagebox.showinfo')
        self.info = self.patch_info.start()
        from ui.pc_ui import PcUI
        self.app = PcUI(self.root,self.content)

    def tearDown(self):
        self.app.audio.stop()
        self.root.destroy()
        self.patch_info.stop()
        self.patch_backend.stop()
        self.directory.cleanup()

    def write_audio(self, path):
        atomic_wave(path,assemble([PCM(24000,b'\x01\0'*2400)],1000,150))

    def prepare_route(self):
        engine = BookEngine(self.content,'roi_grenouille',automatic=True)
        paths = []
        while True:
            path = self.folder/'files'/(engine.current['segment_id']+'.wav')
            self.write_audio(path)
            paths.append(path)
            if engine.finished:
                return paths
            engine.choose(0)
            engine.advance()

    def test_option_is_visible_before_launch_and_playback_runs_to_the_end(self):
        paths = self.prepare_route()
        self.root.geometry('800x620')
        self.root.deiconify()
        self.root.update()
        checks = [w for frame in self.app.page.winfo_children() for w in frame.winfo_children()
                  if w.winfo_class() == 'TCheckbutton']
        self.assertTrue(any(w.winfo_ismapped() and 'Écoute automatique' in w['text'] for w in checks))
        button = next(w for frame in self.app.page.winfo_children() for w in frame.winfo_children()
                      if w.winfo_class() == 'TButton' and w['text'] == 'Ouvrir le Roi-grenouille')
        self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),
                             self.app.page.winfo_rooty()+self.app.page.winfo_height())
        self.app.automatic_options['roi_grenouille'].set(True)
        button.invoke()
        self.assertTrue(self.app.automatic_playback)
        self.assertEqual(self.backend.calls[-1],('start',paths[0]))
        self.assertEqual(len(self.app.actions.winfo_children()),0)
        self.assertNotIn('Que doit faire',self.app.body.get('1.0','end'))
        self.app.choose(1)
        self.app.keyboard_choice(1,'Right')
        self.app.advance()
        self.assertEqual(self.app.engine.current['rank'],1)
        self.backend.current_mode = 'stopped'
        self.app.update_audio_controls()
        self.assertEqual(self.app.engine.current['rank'],2)
        self.app.pause_audio()
        self.app.update_audio_controls()
        self.assertEqual(self.app.engine.current['rank'],2)
        self.assertEqual(self.app.audio.state,'paused')
        self.app.resume_audio()
        self.assertEqual(self.app.engine.current['rank'],2)
        for rank in range(3,12):
            self.backend.current_mode = 'stopped'
            self.app.update_audio_controls()
            self.assertEqual(self.app.engine.current['rank'],rank)
        self.backend.current_mode = 'stopped'
        self.app.update_audio_controls()
        calls = list(self.backend.calls)
        self.app.update_audio_controls()
        self.assertEqual(self.backend.calls,calls)
        self.assertTrue(self.app.automatic_done)
        self.assertEqual(self.app.audio_status['text'],'Écoute terminée')
        self.assertEqual([c['choice_index'] for c in self.app.engine.journal['choices']],[0]*10)
        self.app.restart()
        self.assertTrue(self.app.automatic_playback)
        self.assertEqual(self.app.engine.current['rank'],1)
        self.app.home()
        self.assertIsNone(self.app.audio_poll)
        self.assertFalse(self.app.automatic_playback)

    def test_missing_auto_files_do_not_fall_back_to_interactive_audio(self):
        interactive = BookEngine(self.content,'roi_grenouille')
        self.write_audio(self.folder/'files'/(interactive.current['segment_id']+'.wav'))
        self.assertFalse(self.app.start_book('roi_grenouille',automatic=True))
        self.assertIsNone(self.app.engine)
        self.assertFalse(self.backend.calls)
        self.info.assert_called_once()
        self.assertTrue(self.app.start_book('roi_grenouille'))
        self.assertFalse(self.app.automatic_playback)
        self.assertEqual(len([w for w in self.app.actions.winfo_children() if w.winfo_class()=='TButton']),2)

    def test_missing_audio_during_playback_suspends_until_retry(self):
        paths = self.prepare_route()
        self.app.start_book('roi_grenouille',automatic=True)
        paths[1].unlink()
        self.backend.current_mode = 'stopped'
        self.app.update_audio_controls()
        self.assertEqual(self.app.engine.current['rank'],2)
        self.assertEqual(self.app.audio.state,'unavailable')
        self.app.update_audio_controls()
        self.assertEqual(self.app.engine.current['rank'],2)
        self.assertIn('suspendue',self.app.audio_status['text'])
        self.write_audio(paths[1])
        self.app.resume_audio()
        self.assertEqual(self.app.audio.state,'playing')
        self.backend.current_mode = 'stopped'
        self.app.update_audio_controls()
        self.assertEqual(self.app.engine.current['rank'],3)


if __name__ == '__main__':
    unittest.main()
