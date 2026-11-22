"""Exécuter une demande audio du panneau sur un worker Linux par SSH."""
import argparse
import json
from pathlib import Path, PurePosixPath
import shlex
import shutil
import subprocess
import sys
import tarfile
import uuid

from engine.content import Content, ROOT


def load_config(path):
    config = Content.read(path)
    if not isinstance(config,dict):
        raise ValueError('sessions/audio_worker.json doit contenir un objet JSON.')
    target = str(config.get('target', '')).strip()
    remote_root = str(config.get('root', '')).strip()
    python = str(config.get('python', '')).strip()
    if not target or target.startswith('-') or any(c.isspace() for c in target):
        raise ValueError('Configurer target dans sessions/audio_worker.json (ex. edouard@debianPC).')
    if not remote_root.startswith('/') or any(c.isspace() for c in remote_root):
        raise ValueError('root doit être un chemin absolu Linux du PC fixe.')
    if not python.startswith('/') or any(c.isspace() for c in python):
        raise ValueError('python doit être le chemin absolu de .venv-tts/bin/python sur Debian.')
    threads = config.get('threads', 4)
    if type(threads) is not int or not 1 <= threads <= 32:
        raise ValueError('threads doit être un entier entre 1 et 32.')
    return dict(target=target, root=remote_root.rstrip('/'), python=python, threads=threads)


def source_files(root):
    """Fichiers éditoriaux et code à synchroniser, sans modèles ni caches."""
    root = Path(root).resolve()
    files = set()
    for folder in ('audio', 'engine', 'tools'):
        for path in (root/folder).rglob('*.py'):
            relative = path.relative_to(root)
            if (path.is_file() and not (relative.parts[0] == 'audio' and len(relative.parts) > 1
                                        and relative.parts[1] in ('runtime','experiments'))):
                files.add(path)
    files.update(p for p in (root/'content').rglob('*') if p.is_file())
    files.update(root/p for p in ('config.json', 'audio/emotion_profiles.json',
                                  'audio/generation_settings.json', 'chatterbox/Recording.wav')
                 if (root/p).is_file())
    return sorted(files)


def create_source_archive(root, destination):
    root = Path(root).resolve()
    with tarfile.open(destination, 'w:gz') as archive:
        for path in source_files(root):
            name = path.relative_to(root).as_posix()
            if name == 'audio/generation_settings.json':
                settings = Content.read(path)
                review = settings.get('asr_review_model')
                if isinstance(review, str):
                    settings['asr_review_model'] = review.replace('\\', '/')
                data = json.dumps(settings, ensure_ascii=False, indent=2).encode('utf-8')+b'\n'
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = path.stat().st_mode & 0o777
                import io
                archive.addfile(info, io.BytesIO(data))
            else:
                archive.add(path, arcname=name, recursive=False)


def safe_extract(archive_path, root):
    root = Path(root).resolve()
    with tarfile.open(archive_path, 'r:gz') as archive:
        for item in archive.getmembers():
            if not item.isfile():
                raise ValueError('Archive distante inattendue : seuls les fichiers ordinaires sont acceptés.')
            target = (root/item.name).resolve()
            if not target.is_relative_to(root):
                raise ValueError('L’archive distante contient un chemin hors du projet.')
        archive.extractall(root, filter='data')


def run_remote(root, config_path, request_id, book, generator_args):
    root = Path(root).resolve()
    config = load_config(config_path)
    if not shutil.which('ssh') or not shutil.which('scp'):
        raise ValueError('OpenSSH (ssh et scp) est requis sur le portable.')
    if not request_id or any(c not in '0123456789abcdef-' for c in request_id.lower()):
        raise ValueError('Identifiant de tâche distante invalide.')
    generator_args = list(generator_args)
    if generator_args and generator_args[0] == '--':
        generator_args = generator_args[1:]
    if '--threads' not in generator_args:
        generator_args += ['--threads', str(config['threads'])]
    report_path = None
    for index, value in enumerate(generator_args[:-1]):
        if value == '--report':
            local_path = Path(generator_args[index+1]).resolve()
            if not local_path.is_relative_to(root):
                raise ValueError('Le rapport sort du dossier du projet.')
            generator_args[index+1] = str(PurePosixPath(config['root']) /
                                           PurePosixPath(local_path.relative_to(root).as_posix()))
            report_path = generator_args[index+1]

    upload_relative = f'.remote_admin/uploads/{request_id}.tar.gz'
    result_relative = f'.remote_admin/results/{request_id}.tar.gz'
    local_archive = root/'tmp'/f'remote-source-{request_id}.tar.gz'
    local_result = root/'tmp'/f'remote-result-{request_id}.tar.gz'
    local_archive.parent.mkdir(parents=True, exist_ok=True)
    try:
        create_source_archive(root, local_archive)
        remote_upload = f"{config['root']}/{upload_relative}"
        mkdir = f"mkdir -p {shlex.quote(config['root'])}/.remote_admin/uploads {shlex.quote(config['root'])}/.remote_admin/results"
        checked_ssh(config, mkdir)
        subprocess.run(['scp', '-q', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                        str(local_archive), f"{config['target']}:{remote_upload}"],
                       check=True, timeout=120)
        remote_command = [config['python'], '-m', 'engine.remote_audio_worker', 'run',
                          '--root', config['root'], '--request-id', request_id,
                          '--book', book, '--source-archive', remote_upload]
        if report_path:
            remote_command += ['--report-path', report_path]
        remote_command += ['--']+generator_args
        shell = (f"cd {shlex.quote(config['root'])} && "+
                 f"{shlex.join(remote_command)}")
        code = subprocess.run(['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                               config['target'], shell], check=False).returncode
        remote_result = f"{config['target']}:{config['root']}/{result_relative}"
        try:
            subprocess.run(['scp', '-q', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                            remote_result, str(local_result)], check=True, timeout=120)
            safe_extract(local_result, root)
            try:
                acknowledge_remote(config,book)
            except (OSError, subprocess.SubprocessError) as exc:
                print(f'Accusé de réception distant différé : {exc}', file=sys.stderr, flush=True)
        except subprocess.CalledProcessError:
            if code == 0:
                raise
            print('Le worker distant n’a pas pu rapatrier son rapport de fin.', file=sys.stderr, flush=True)
        finally:
            try:
                checked_ssh(config, f"rm -f -- {shlex.quote(config['root']+'/'+result_relative)}")
            except (OSError, subprocess.SubprocessError):
                pass
        return code
    finally:
        for path in (local_archive, local_result):
            try:
                path.unlink()
            except OSError:
                pass


def checked_ssh(config, remote_command, timeout=30):
    subprocess.run(['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                    config['target'], remote_command], check=True, timeout=timeout,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)


def acknowledge_remote(config, book):
    command = [config['python'], '-m', 'engine.remote_audio_worker', 'ack',
               '--root', config['root'], '--request-id', '00000000000000000000000000000000',
               '--book', book]
    checked_ssh(config, f"cd {shlex.quote(config['root'])} && {shlex.join(command)}", timeout=12)


def cancel_remote(config_path, request_id):
    config = load_config(config_path)
    command = [config['python'], '-m', 'engine.remote_audio_worker', 'cancel',
               '--root', config['root'], '--request-id', request_id]
    checked_ssh(config, f"cd {shlex.quote(config['root'])} && {shlex.join(command)}", timeout=12)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--request-id', required=True)
    parser.add_argument('--book', required=True)
    parser.add_argument('generator_args', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        return run_remote(args.root, args.config, args.request_id, args.book, args.generator_args)
    except Exception as exc:
        print(f'Worker SSH : {exc}', file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
