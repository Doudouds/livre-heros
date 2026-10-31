"""Encodage des journaux : UTF-8 en sortie, lecture des anciens Windows-1252."""
import sys


def configure_utf8_output():
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):
            stream.reconfigure(encoding='utf-8',errors='backslashreplace')


def decode_task_log(raw):
    # Un ancien journal peut contenir une reprise ANSI après des lignes UTF-8.
    lines = []
    for line in raw.splitlines(keepends=True):
        try:
            lines.append(line.decode('utf-8'))
        except UnicodeDecodeError:
            lines.append(line.decode('cp1252',errors='replace'))
    return ''.join(lines).removeprefix('\ufeff')


def read_task_log_tail(path, limit):
    with path.open('rb') as stream:
        end = stream.seek(0,2)
        offset = max(0,end-limit)
        if offset:
            stream.seek(offset-1)
            if stream.read(1)!=b'\n':
                # Ne pas décoder une lettre UTF-8 coupée ni une ligne JSON
                # incomplète à la limite de la fenêtre de lecture.
                stream.readline()
        else:
            stream.seek(0)
        return decode_task_log(stream.read())
