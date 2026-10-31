import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from engine.audio_admin import AdminJobs
from engine.content import ROOT
from engine.task_log import configure_utf8_output,decode_task_log,read_task_log_tail


class TaskLogTests(unittest.TestCase):
    def test_utf8_and_legacy_windows_lines_keep_accents_and_unicode(self):
        first='⌛ Vérification : déjà prête.\n'
        last='Terminé : 1 prêts, 0 en échec. État : D:\\livre_heros\n'
        self.assertEqual(decode_task_log(first.encode('utf-8')+last.encode('cp1252')),first+last)
        self.assertEqual(decode_task_log((first+last).encode('utf-8')),first+last)

    def test_output_is_utf8_even_when_inherited_stream_is_windows_1252(self):
        buffer=io.BytesIO();stream=io.TextIOWrapper(buffer,encoding='cp1252',newline='\n')
        with patch('engine.task_log.sys.stdout',stream),patch('engine.task_log.sys.stderr',stream):
            configure_utf8_output()
            stream.write('Terminé : prêt, échec, état, ⌛\n');stream.flush()
        self.assertEqual(buffer.getvalue(),'Terminé : prêt, échec, état, ⌛\n'.encode('utf-8'))

    def test_tail_does_not_cut_an_accent_or_lose_a_complete_line(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            path=Path(folder)/'journal.log'
            path.write_bytes('Début : vérifié\nTerminé : prêt.\n'.encode('utf-8'))
            content=path.read_bytes();last='Terminé : prêt.\n'
            # Le début de la fenêtre tombe sur le second octet d'un é.
            start=content.index('é'.encode('utf-8'))+1
            self.assertEqual(read_task_log_tail(path,len(content)-start),last)
            self.assertEqual(read_task_log_tail(path,len(last.encode('utf-8'))),last)

    def test_admin_displays_legacy_log_without_modifying_its_bytes(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            root=Path(folder);path=root/'journal.log'
            message='Terminé : 1 prêts, 0 en échec. État : rapport.json\n'
            raw=message.encode('cp1252');path.write_bytes(raw)
            jobs=AdminJobs(root);jobs.current={'log':str(path)}
            self.assertEqual(jobs.log_tail(),message.strip())
            self.assertEqual(path.read_bytes(),raw)

    def test_launcher_keeps_utf8_when_parent_requests_legacy_encoding(self):
        import os
        result=subprocess.run([sys.executable,str(ROOT/'generer_audio_conte.py'),'--help'],
                              cwd=ROOT,env=dict(os.environ,PYTHONIOENCODING='cp1252'),capture_output=True,timeout=20)
        self.assertEqual(result.returncode,0)
        text=result.stdout.decode('utf-8')
        self.assertIn('Générer',text)
        self.assertNotIn('\ufffd',text)


if __name__=='__main__':unittest.main()
