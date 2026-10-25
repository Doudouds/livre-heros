import copy
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from audio.speech_verification import compare_transcript
from audio.styled_generation import StyledRun
from audio.tts_batch import atomic_json, file_hash, read_wave, receipt_path
from audio.voice_markup import compile_book, parse_markup, render_markup
from engine.book_engine import BookEngine
from engine.content import Content, ROOT, segment_id
from tests.test_tts_batch import FakeVoice
from tools.generate_faithful_audio import parser as old_parser, plan_segment
from tools.generate_story_audio import main, parser, plans_for_book, voice_snapshot


class Verifier:
    def __init__(self, fail_full=0, fail_chunk=0):
        self.fail_full,self.fail_chunk = fail_full,fail_chunk

    def verify(self, expected, pcm, *, vad_filter=False):
        if vad_filter and self.fail_full:
            self.fail_full -= 1
            return compare_transcript(expected,expected.rsplit(' ',1)[0])
        if not vad_filter and self.fail_chunk:
            self.fail_chunk -= 1
            return compare_transcript(expected,expected.rsplit(' ',1)[0])
        return compare_transcript(expected,expected)


def fake_plan(folder, number=1, paragraphs=None):
    texts = paragraphs or ['La princesse regarde la fontaine avant de parler.']
    text = ' '.join(texts)
    key = segment_id('test_'+str(number),'narration',text)
    return dict(book='test',scene_id='test_'+str(number),segment_id=key,title='Test',text=text,
                spans=[dict(text=t,speaker='narrateur',emotion='neutral',
                            parameters=dict(exaggeration=.4,cfg_weight=.3)) for t in texts],
                output_file=str(folder/'files'/(key+'.wav')),lead_in_ms=1000,pause_ms=150,
                palette_sha256='palette',palette_source='test',chunk_chars=300,seed=20261018)


def runner(folder, fake=None, verifier=None, **overrides):
    fake,verifier = fake or FakeVoice(),verifier or Verifier()
    settings = dict(cache_dir=folder/'cache',output_dir=folder/'files',report=folder/'status.json',
                    voice_sha='reference-A',model={'model':'test'},environment={'test':1},threads=8,
                    backend_factory=lambda parameters:fake,verifier_factory=lambda:verifier,
                    verifier_identity={'checker':'test'},attempts=3,progress=lambda message:None)
    settings.update(overrides)
    return StyledRun(**settings)


class MarkupTests(unittest.TestCase):
    def test_markup_roundtrip_preserves_punctuation_paragraphs_and_xml_characters(self):
        text = 'Elle dit : « Soleil & lune < étoiles. »\n\nPuis elle sourit.'
        spans = [dict(text=text.split('\n\n')[0],emotion='tristesse'),
                 dict(text=text.split('\n\n')[1],emotion='joie')]
        markup = render_markup(text,spans)
        plain,parsed = parse_markup(markup,{'tristesse':{},'joie':{}})
        self.assertEqual(plain,text)
        self.assertEqual([s['emotion'] for s in parsed],['tristesse','joie'])
        for bad in ('Texte sans balise.', '<voix emotion="inconnue">Bonjour.</voix>',
                    '<voix emotion="joie">Bonjour.',
                    '<voix emotion="joie"><voix emotion="joie">Bonjour.</voix></voix>',
                    '<voix emotion="joie">Bonjour.</voix> Des mots oubliés.',
                    '<!DOCTYPE audio><voix emotion="joie">Bonjour.</voix>'):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                parse_markup(bad,{'joie':{}})

    def test_compiler_rejects_text_changes_and_missing_consequence_annotation(self):
        book = copy.deepcopy(Content().books['roi_grenouille'])
        profiles = Content.read(ROOT/'audio/emotion_profiles.json')['profiles']
        book['scenes'][0]['audio_markup'] = book['scenes'][0]['audio_markup'].replace('vivait un roi','vivait un prince')
        with self.assertRaisesRegex(ValueError,'modifie le texte'):
            compile_book(book,profiles)
        book = copy.deepcopy(Content().books['roi_grenouille'])
        del book['scenes'][0]['choices'][1]['consequence_audio_markup']
        with self.assertRaisesRegex(ValueError,'manquant'):
            compile_book(book,profiles)


class StoryPlanningTests(unittest.TestCase):
    def test_every_route_has_the_exact_runtime_text_and_all_consequences_are_voiced(self):
        content = Content()
        args = parser().parse_args(['--dry-run'])
        args.output_dir = ROOT/'audio/experiments/roi_grenouille/files'
        plans = plans_for_book(args,content)
        self.assertEqual(len(plans),21)
        by_id = {p['segment_id']:p for p in plans}
        for route in itertools.product((0,1),repeat=10):
            engine = BookEngine(content,'roi_grenouille')
            for choice in (*route,None):
                current = engine.current
                plan = by_id[current['segment_id']]
                self.assertEqual(plan['text'],current['spoken_text'])
                self.assertEqual(' '.join(' '.join(s['text'].split()) for s in plan['spans']),
                                 ' '.join(current['spoken_text'].split()))
                self.assertNotIn('<voix',current['spoken_text'])
                if choice is not None:
                    engine.choose(choice)
                    engine.advance()

    def test_first_segment_plan_matches_the_shared_story_planner(self):
        args = parser().parse_args(['--segment','1'])
        args.output_dir = ROOT/'audio/experiments/roi_grenouille/files'
        self.assertEqual(plans_for_book(args)[0],plan_segment(old_parser().parse_args([])))

    def test_dry_run_has_no_torch_requirement_and_does_not_touch_completed_status(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as temporary:
            folder = Path(temporary)
            status = folder/'status.json'
            status.write_text('completed status',encoding='utf-8')
            with patch.dict('sys.modules',{'torch':None,'chatterbox':None}),patch('builtins.print'):
                self.assertEqual(main(['--dry-run','--report',str(status),'--output-dir',str(folder/'files')]),0)
            self.assertEqual(status.read_text(encoding='utf-8'),'completed status')
            self.assertFalse((folder/'files').exists())
            self.assertEqual(len(json.loads((folder/'audio_plan.json').read_text(encoding='utf-8'))['segments']),21)


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT/'tmp')
        self.folder = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_finished_run_is_preserved_without_loading_tts_or_asr(self):
        plans = [fake_plan(self.folder)]
        first = runner(self.folder)
        self.assertEqual(first.run(plans),0)
        original = file_hash(plans[0]['output_file'])
        forbidden = lambda *args:self.fail('Un fichier complet ne doit pas charger les modèles.')
        second = runner(self.folder,backend_factory=forbidden,verifier_factory=forbidden)
        self.assertEqual(second.run(plans),0)
        self.assertEqual(file_hash(plans[0]['output_file']),original)
        self.assertTrue(second.state['segments'][0]['reused'])
        pcm = read_wave(plans[0]['output_file'])
        self.assertEqual(pcm.frames[:pcm.sample_rate*2],b'\0'*(pcm.sample_rate*2))

    def test_incompatible_voice_is_refused_before_other_outputs_or_status_are_changed(self):
        plan = fake_plan(self.folder)
        runner(self.folder).run([plan])
        before = (self.folder/'status.json').read_bytes()
        another = fake_plan(self.folder,2)
        with self.assertRaisesRegex(ValueError,'Voix, texte balisé'):
            runner(self.folder,voice_sha='reference-B').run([another,plan])
        self.assertEqual((self.folder/'status.json').read_bytes(),before)
        self.assertFalse(Path(another['output_file']).exists())

    def test_corrupt_final_is_reassembled_from_verified_chunks_without_synthesis(self):
        plan = fake_plan(self.folder)
        runner(self.folder).run([plan])
        before = file_hash(plan['output_file'])
        Path(plan['output_file']).write_bytes(b'RIFF broken')
        resumed = runner(self.folder,backend_factory=lambda *args:self.fail('Prises déjà vérifiées.'))
        self.assertEqual(resumed.run([plan]),0)
        self.assertEqual(file_hash(plan['output_file']),before)

    def test_interrupt_between_final_wav_and_receipt_is_recoverable(self):
        plan = fake_plan(self.folder)
        with patch('audio.styled_generation.write_receipt',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                runner(self.folder).run([plan])
        pending = Path(plan['output_file']+'.pending.json')
        self.assertTrue(pending.is_file())
        self.assertTrue(Path(plan['output_file']).is_file())
        resumed = runner(self.folder,backend_factory=lambda *args:self.fail('Ne pas refaire les prises.'))
        self.assertEqual(resumed.run([plan]),0)
        self.assertFalse(pending.exists())

    def test_rejected_chunk_is_retried_with_new_seeds(self):
        plan = fake_plan(self.folder)
        voice = FakeVoice()
        self.assertEqual(runner(self.folder,voice,Verifier(fail_chunk=1)).run([plan]),0)
        self.assertEqual(len(voice.calls),2)
        self.assertNotEqual(voice.calls[0][1],voice.calls[1][1])

    def test_full_rejection_uses_separate_cache_round_and_can_then_finish(self):
        plan = fake_plan(self.folder)
        voice = FakeVoice()
        run = runner(self.folder,voice,Verifier(fail_full=1))
        self.assertEqual(run.run([plan]),0)
        self.assertEqual(run.state['segments'][0]['round'],1)
        self.assertEqual(len(voice.calls),2)
        self.assertNotEqual(voice.calls[0][1],voice.calls[1][1])
        self.assertEqual(len(list((self.folder/'cache').glob('*/rejected_full/*.wav'))),1)

    def test_exhausted_full_retries_are_not_ready_and_next_run_uses_next_round(self):
        plan = fake_plan(self.folder)
        run = runner(self.folder,verifier=Verifier(fail_full=10),attempts=2)
        self.assertEqual(run.run([plan]),1)
        self.assertFalse(Path(plan['output_file']).exists())
        self.assertEqual(run.state['failed'],1)
        resumed = runner(self.folder)
        self.assertEqual(resumed.run([plan]),0)
        self.assertEqual(resumed.state['segments'][0]['round'],2)

    def test_reference_copy_is_frozen_and_fingerprinted(self):
        from audio.tts_batch import PCM, atomic_wave
        source = self.folder/'voice.wav'
        atomic_wave(source,PCM(8000,b'\x01\0'*32000))
        target,sha = voice_snapshot(source,self.folder/'cache')
        self.assertEqual(file_hash(target),sha)
        source.write_bytes(b'new reference')
        self.assertEqual(file_hash(target),sha)

    def test_hard_process_death_releases_locks_and_resumes_only_missing_chunks(self):
        plans = [fake_plan(self.folder,1),fake_plan(self.folder,2,
                 ['Le roi ouvre la porte du château.','La grenouille entre dans la grande salle.',
                  'La princesse rejoint la table du roi.'])]
        atomic_json(self.folder/'plans.json',plans)
        child = r'''
import json,os,sys
from pathlib import Path
from tests.test_story_audio import runner,Verifier
from tests.test_tts_batch import FakeVoice
folder=Path(sys.argv[1])
class CrashVoice(FakeVoice):
    def synthesize(self,text,seed):
        with (folder/'calls.jsonl').open('a',encoding='utf-8') as out:
            out.write(json.dumps([text,seed])+'\n')
            out.flush()
        if sys.argv[2]=='crash' and len(self.calls)==2:
            os._exit(23)
        return super().synthesize(text,seed)
plans=json.loads((folder/'plans.json').read_text(encoding='utf-8'))
raise SystemExit(runner(folder,CrashVoice(),Verifier()).run(plans))
'''
        crashed = subprocess.run([sys.executable,'-c',child,str(self.folder),'crash'],cwd=ROOT,capture_output=True,timeout=30)
        self.assertEqual(crashed.returncode,23,crashed.stderr.decode(errors='replace'))
        first_hash = file_hash(plans[0]['output_file'])
        resumed = subprocess.run([sys.executable,'-c',child,str(self.folder),'resume'],cwd=ROOT,capture_output=True,timeout=30)
        self.assertEqual(resumed.returncode,0,resumed.stderr.decode(errors='replace'))
        self.assertEqual(first_hash,file_hash(plans[0]['output_file']))
        calls = [json.loads(line) for line in (self.folder/'calls.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(sum(t==plans[0]['text'] for t,_ in calls),1)
        self.assertEqual(sum(t==plans[1]['spans'][0]['text'] for t,_ in calls),1)
        interrupted_text = plans[1]['spans'][1]['text']
        seeds = [seed for text,seed in calls if text==interrupted_text]
        self.assertEqual(len(seeds),2)
        self.assertNotEqual(seeds[0],seeds[1])


if __name__ == '__main__':
    unittest.main()
