import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
import tarfile
from unittest.mock import patch, PropertyMock

from engine.remote_audio import create_source_archive, load_config, safe_extract
from engine.remote_audio_worker import changed_files
import engine.remote_audio_worker as worker
from engine.audio_admin import AdminJobs, AudioInventory
from engine.content import ROOT


class RemoteAudioTests(unittest.TestCase):
    def test_source_archive_contains_live_code_but_not_platform_caches(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('audio','engine','tools','content/books','chatterbox',
                         'audio/runtime/asr_dependencies','audio/experiments/book/files'):
                (root/name).mkdir(parents=True,exist_ok=True)
            (root/'audio/tts_batch.py').write_text('code',encoding='utf-8')
            (root/'engine/remote_audio_worker.py').write_text('worker',encoding='utf-8')
            (root/'tools/generate_story_audio.py').write_text('generator',encoding='utf-8')
            (root/'content/books/book.json').write_text('{}',encoding='utf-8')
            (root/'audio/runtime/asr_dependencies/platform.pyd').write_text('windows',encoding='utf-8')
            (root/'audio/experiments/book/files/old.wav').write_bytes(b'audio')
            (root/'audio/emotion_profiles.json').write_text('{}',encoding='utf-8')
            (root/'audio/generation_settings.json').write_text(json.dumps(
                {'asr_review_model':r'audio\runtime\asr_models\medium'}),encoding='utf-8')
            (root/'config.json').write_text('{}',encoding='utf-8')
            archive_path = root/'source.tar.gz'
            create_source_archive(root,archive_path)
            with tarfile.open(archive_path,'r:gz') as archive:
                names=set(archive.getnames())
                self.assertIn('engine/remote_audio_worker.py',names)
                self.assertIn('content/books/book.json',names)
                self.assertNotIn('audio/runtime/asr_dependencies/platform.pyd',names)
                self.assertNotIn('audio/experiments/book/files/old.wav',names)
                settings=json.load(archive.extractfile('audio/generation_settings.json'))
                self.assertEqual(settings['asr_review_model'],'audio/runtime/asr_models/medium')

    def test_local_extraction_rejects_paths_outside_project(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            archive_path=root/'unsafe.tar'
            with tarfile.open(archive_path,'w:gz') as archive:
                member=tarfile.TarInfo('../outside.txt')
                member.size=1
                import io
                archive.addfile(member,io.BytesIO(b'x'))
            with self.assertRaises(ValueError):
                safe_extract(archive_path,root)

    def test_worker_config_and_targeted_report_delta(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            config_path=root/'worker.json'
            config_path.write_text(json.dumps({'target':'edouard@debianPC',
                'root':'/home/edouard/livre-heros-worker',
                'python':'/home/edouard/livre-heros-worker/.venv-tts/bin/python','threads':4}),encoding='utf-8')
            self.assertEqual(load_config(config_path)['threads'],4)
            report=root/'reports/admin/jobs/request/interactive/generation_status.json'
            report.parent.mkdir(parents=True)
            report.write_text('{}',encoding='utf-8')
            paths=changed_files(root,'book',time.time_ns()-1_000_000_000,'request',str(report))
            self.assertIn(report,paths)

    def test_admin_routes_selected_tone_to_remote_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            config=Path(temp)/'worker.json'
            config.write_text(json.dumps({'target':'edouard@debianPC',
                'root':'/home/edouard/livre-heros-worker',
                'python':'/home/edouard/livre-heros-worker/.venv-tts/bin/python','threads':4}),encoding='utf-8')
            row=AudioInventory().rows('roi_grenouille')[0]
            jobs=AdminJobs(ROOT)
            with patch.object(AdminJobs,'remote_config_path',new_callable=PropertyMock,return_value=config), \
                 patch.object(jobs,'start') as start:
                jobs.start_audio('roi_grenouille',segment_id=row['plan']['segment_id'],regenerate=True,
                                 spans=[2],emotion='joie')
                specs=start.call_args.args[2](ROOT/'reports/admin/fake-remote-job')
            command=specs[0]['command']
            self.assertEqual(command[:3],[sys.executable,'-m','engine.remote_audio'])
            self.assertIn('--span',command)
            self.assertIn('joie',command)
            self.assertEqual(specs[0]['remote']['target'],'edouard@debianPC')

    def test_remote_worker_separates_its_options_from_generator_arguments(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(worker,'run',return_value=0) as run:
                result=worker.main(['run','--root',temp,'--request-id','a'*32,
                    '--book','roi_grenouille','--source-archive','source.tar.gz',
                    '--report-path',temp+'/reports/status.json','--',
                    '--book','roi_grenouille','--dry-run'])
            self.assertEqual(result,0)
            self.assertEqual(run.call_args.args[-1],['--book','roi_grenouille','--dry-run'])


if __name__=='__main__':
    unittest.main()
