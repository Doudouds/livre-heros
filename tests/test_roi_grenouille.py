import copy
import itertools
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from audio.tts_batch import PCM, file_hash, read_wave, atomic_wave
from engine.book_engine import BookEngine, validate_book
from engine.content import Content, ROOT
from tools.generate_faithful_audio import assemble, main as audio_main, parser, plan_segment


class FrogTaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content()
        cls.book = cls.content.books['roi_grenouille']

    def test_source_is_preserved_in_full_and_in_the_same_order(self):
        validate_book(self.book,ROOT)
        canonical = (ROOT/self.book['source']['canonical_text']).read_text(encoding='utf-8')
        normalize = lambda text:' '.join(text.split())
        self.assertEqual(normalize(' '.join(s['text'] for s in self.book['scenes'])),normalize(canonical))
        self.assertEqual(file_hash(ROOT/self.book['source']['file']),self.book['source']['sha256'])
        self.assertEqual(self.book['source']['pages'],[14,15])
        self.assertIn('la projeta de toutes ses forces contre le mur',canonical)
        self.assertIn('les cercles de fer du fidèle Henri',canonical)
        self.assertNotIn('un baiser',canonical)

    def test_all_1024_routes_reach_the_same_canonical_ending(self):
        expected = [s['id'] for s in self.book['scenes']]
        for choices in itertools.product((0,1),repeat=10):
            engine = BookEngine(self.content,'roi_grenouille')
            visited = [engine.current['id']]
            for choice in choices:
                self.assertEqual(len(engine.current['choices']),2)
                result = engine.choose(choice)
                engine.advance()
                self.assertTrue(engine.current['text'].startswith(result['text']+'\n\n'))
                visited.append(engine.current['id'])
            self.assertTrue(engine.finished)
            self.assertEqual(engine.state.story_progress,10)
            self.assertEqual(visited,expected)
            self.assertTrue(engine.current['text'].endswith('heureux de voir son seigneur délivré.'))

    def test_narrator_is_third_person_and_question_follows_the_character(self):
        self.assertEqual(self.book['narrative_person'],3)
        prose = '\n'.join(s['text'] for s in self.book['scenes'])
        prose = re.sub(r'«.*?»','',prose,flags=re.S)
        self.assertIsNone(re.search(r'\b(tu|toi|vous|votre)\b',prose,re.I))
        engine = BookEngine(self.content,'roi_grenouille')
        self.assertEqual(engine.current['choice_question'],'Que doit faire la princesse ?')
        for _ in range(9):
            engine.choose(0)
            engine.advance()
        self.assertEqual(engine.current['choice_question'],'Que doit faire le prince ?')

    def test_journal_replays_choices_without_changing_the_tale(self):
        engine = BookEngine(self.content,'roi_grenouille')
        for choice in (0,1,0,1,1):
            engine.choose(choice)
            engine.advance()
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            target = Path(folder)/'session.json'
            engine.export_session(target)
            replay = BookEngine.replay(self.content,target)
        self.assertEqual(replay.current,engine.current)
        self.assertEqual(replay.debug_snapshot(),engine.debug_snapshot())

    def test_first_audio_plan_matches_runtime_and_approved_emotions(self):
        args = parser().parse_args(['--dry-run'])
        plan = plan_segment(args,self.content)
        engine = BookEngine(self.content,'roi_grenouille')
        self.assertEqual(plan['text'],engine.current['spoken_text'])
        self.assertEqual(Path(plan['output_file']).stem,engine.current['segment_id'])
        self.assertEqual(' '.join(' '.join(s['text'].split()) for s in plan['spans']),
                         ' '.join(plan['text'].split()))
        self.assertEqual({s['emotion'] for s in plan['spans']},
                         {'neutral','emerveillement','tristesse','tendresse','surprise'})
        self.assertEqual(plan['spans'][-1]['role'],'choix')
        self.assertIn('Choix 1 :',plan['spans'][-1]['text'])
        self.assertIn('Ou choix 2 :',plan['spans'][-1]['text'])
        approved = Content.read(ROOT/'audio/experiments/emotions/essai_03_e12fed44e64c/plan.json')
        profiles = {i['id']:i['parameters'] for i in approved['excerpts']}
        self.assertEqual(plan['spans'][0]['role'],'introduction')
        self.assertEqual(plan['spans'][1]['parameters'],profiles['05_emerveillement'])

    def test_exactly_one_second_is_embedded_before_any_speech(self):
        first, second = PCM(24000,b'\x01\x02'*2400),PCM(24000,b'\x03\x04'*2400)
        pcm = assemble([first,second],1000,150)
        self.assertEqual(pcm.frames[:48000],b'\0'*48000)
        self.assertEqual(pcm.frames[48000:],first.frames+b'\0'*7200+second.frames)
        self.assertEqual(self.book['audio_lead_in_ms'],0)
        with self.assertRaises(ValueError):
            assemble([first,PCM(16000,second.frames)],1000,150)

    def test_dry_run_creates_only_the_plan_without_tts_or_other_segments(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            directory = Path(folder)
            with patch.dict('sys.modules',{'torch':None,'chatterbox':None}),patch('builtins.print'):
                self.assertEqual(audio_main(['--dry-run','--output-dir',str(directory/'files'),
                                             '--report',str(directory/'plan.json')]),0)
            plan = json.loads((directory/'plan.json').read_text(encoding='utf-8'))
            self.assertEqual(plan['scene_id'],'roi_grenouille_01')
            self.assertFalse((directory/'files').exists())


class FrogTaleUITests(unittest.TestCase):
    def test_library_launch_restart_and_audio_do_not_open_the_passeuse(self):
        import tkinter as tk
        from tests.test_pc_audio_tts import FakeWindowsWave
        from ui.pc_ui import PcUI
        content = Content()
        root = tk.Tk()
        root.withdraw()
        root.attributes('-alpha',0)
        app = None
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            directory = Path(folder)
            segment = BookEngine(content,'roi_grenouille').current['segment_id']
            wave = directory/(segment+'.wav')
            atomic_wave(wave,assemble([PCM(24000,b'\x01\x02'*2400)],1000,150))
            config = copy.deepcopy(content.config)
            config['audio_root'] = directory.relative_to(ROOT).as_posix()+'/legacy'
            config['book_audio_roots']['roi_grenouille'] = directory.relative_to(ROOT).as_posix()
            content.config = config
            backend = FakeWindowsWave()
            try:
                with patch('audio.audio_player.WindowsWavePlayer',return_value=backend):
                    app = PcUI(root,content)
                    root.geometry('800x620')
                    root.deiconify()
                    root.update()
                    button = next(w for frame in app.page.winfo_children() for w in frame.winfo_children()
                                  if w.winfo_class()=='TButton' and w['text']=='Ouvrir le Roi-grenouille')
                    self.assertTrue(button.winfo_ismapped())
                    self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),
                                         app.page.winfo_rooty()+app.page.winfo_height())
                    button.invoke()
                    root.update()
                    self.assertEqual(app.engine.book['id'],'roi_grenouille')
                    self.assertEqual(app.audio.state,'playing')
                    self.assertEqual(backend.calls[-1],('start',wave))
                    self.assertEqual(read_wave(backend.calls[-1][1]).frames[:48000],b'\0'*48000)
                    self.assertIsNotNone(app.audio_controls)
                    self.assertIsNone(app.original_illustration)
                    app.choose(1)
                    self.assertEqual(app.engine.current['rank'],2)
                    self.assertEqual(app.audio.state,'unavailable')
                    app.restart()
                    self.assertEqual(app.engine.book['id'],'roi_grenouille')
                    for _ in range(10):
                        app.choose(0)
                    self.assertTrue(app.engine.finished)
                    labels = [str(w['text']) for w in app.actions.winfo_children() if w.winfo_class()=='TLabel']
                    self.assertTrue(any('Fin du conte' in text for text in labels))
                    self.assertFalse(any('chapitre 2' in text for text in labels))
                    app.restart()
                    self.assertEqual(app.engine.current['id'],'roi_grenouille_01')
            finally:
                if app:
                    app.audio.stop()
                root.destroy()


if __name__ == '__main__':
    unittest.main()
