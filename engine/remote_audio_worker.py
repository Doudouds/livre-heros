"""Worker Linux appelé par le panneau via SSH ; aucune dépendance graphique."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import signal
import subprocess
import sys
import tarfile
import time


def safe_extract(archive_path, root):
    root = Path(root).resolve()
    with tarfile.open(archive_path, 'r:gz') as archive:
        for item in archive.getmembers():
            if not item.isfile():
                raise ValueError('Archive source inattendue.')
            target = (root/item.name).resolve()
            if not target.is_relative_to(root):
                raise ValueError('Archive source hors du projet.')
        archive.extractall(root, filter='data')


def cancel(root, request_id):
    pid_file = Path(root)/'.remote_admin/jobs'/f'{request_id}.json'
    try:
        state = json.loads(pid_file.read_text(encoding='utf-8'))
        os.killpg(int(state['pgid']), signal.SIGTERM)
        print('Arrêt demandé au processus audio distant.', flush=True)
        return 0
    except FileNotFoundError:
        print('Aucun processus distant actif pour cette demande.', flush=True)
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f'Arrêt distant impossible : {exc}', file=sys.stderr, flush=True)
        return 1


def changed_files(root, book, since_ns, request_id, report_path=None):
    root = Path(root)
    candidates = [root/'audio/experiments'/book, root/'reports'/book,
                  root/'reports/admin/jobs'/request_id]
    if report_path:
        report = (root/PurePosixPath(report_path)).resolve()
        if report.is_relative_to(root.resolve()):
            candidates.append(report.parent)
    result = []
    for folder in candidates:
        if folder.is_dir():
            for path in folder.rglob('*'):
                try:
                    if path.is_file() and path.stat().st_mtime_ns >= since_ns-2_000_000_000:
                        result.append(path)
                except OSError:
                    continue
    return sorted(set(result))


def sync_marker(root, book):
    folder=Path(root)/'.remote_admin/sync'
    folder.mkdir(parents=True,exist_ok=True)
    return folder/f'{book}.json'


def acknowledge(root, book):
    if not book or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in book):
        raise ValueError('Identifiant de conte distant invalide.')
    marker=sync_marker(root,book)
    marker.write_text(json.dumps({'last_synced_ns':time.time_ns()}),encoding='utf-8')
    return 0


def run(root, request_id, book, source_archive, report_path, generator_args):
    root = Path(root).resolve()
    if not request_id or any(c not in '0123456789abcdef-' for c in request_id.lower()):
        raise ValueError('Identifiant distant invalide.')
    if not book or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in book):
        raise ValueError('Identifiant de conte distant invalide.')
    archive_path = Path(source_archive)
    if not archive_path.is_absolute():
        archive_path = root/archive_path
    safe_extract(archive_path, root)
    archive_path.unlink(missing_ok=True)
    generator_args = list(generator_args)
    if generator_args and generator_args[0] == '--':
        generator_args = generator_args[1:]
    if not generator_args or generator_args[0] != '--book' or book not in generator_args:
        raise ValueError('Commande audio distante inattendue.')
    python = Path(sys.executable)
    # Le worker est lancé avec l’interpréteur configuré par le portable.
    marker=sync_marker(root,book)
    if marker.is_file():
        try:
            since_ns=int(json.loads(marker.read_text(encoding='utf-8'))['last_synced_ns'])
        except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError):
            since_ns=0
    else:
        # La copie initiale du worker provient du portable ; seuls ses résultats
        # postérieurs à cette mise en place doivent être rapatriés.
        since_ns=time.time_ns()
        marker.write_text(json.dumps({'last_synced_ns':since_ns}),encoding='utf-8')
    state_dir = root/'.remote_admin/jobs'
    state_dir.mkdir(parents=True, exist_ok=True)
    pid_file = state_dir/f'{request_id}.json'
    output_dir = root/'.remote_admin/results'
    output_dir.mkdir(parents=True, exist_ok=True)
    result_archive = output_dir/f'{request_id}.tar.gz'
    proc = None
    code = 1
    try:
        proc = subprocess.Popen([str(python), '-m', 'tools.generate_story_audio', *generator_args],
                                cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                                bufsize=1, start_new_session=True)
        pid_file.write_text(json.dumps({'pid':proc.pid,'pgid':proc.pid}), encoding='utf-8')
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
        code = proc.wait()
    except (KeyboardInterrupt, BrokenPipeError):
        if proc and proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=20)
        code = 130
    finally:
        pid_file.unlink(missing_ok=True)
        files = changed_files(root, book, since_ns, request_id, report_path)
        with tarfile.open(result_archive, 'w:gz') as archive:
            for path in files:
                archive.add(path, arcname=path.relative_to(root).as_posix(), recursive=False)
        print(f'\nRésultats préparés : {len(files)} fichiers à rapatrier.', flush=True)
    return code


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    if not argv or argv[0] not in ('run','cancel','ack'):
        parser.error('indiquer run, cancel ou ack')
    action=argv.pop(0)
    if action == 'run':
        if '--' in argv:
            separator=argv.index('--')
            options,generator_args=argv[:separator],argv[separator+1:]
        else:
            options,generator_args=argv,[]
    else:
        options,generator_args=argv,[]
    parser.add_argument('--root', required=True)
    parser.add_argument('--request-id', required=True)
    parser.add_argument('--book', default='')
    parser.add_argument('--source-archive', default='')
    parser.add_argument('--report-path', default='')
    args = parser.parse_args(options)
    try:
        if action == 'cancel':
            return cancel(args.root, args.request_id)
        if action == 'ack':
            if not args.book:
                raise ValueError('Le nom du conte est requis pour accuser réception.')
            return acknowledge(args.root,args.book)
        return run(args.root,args.request_id,args.book,args.source_archive,args.report_path,generator_args)
    except Exception as exc:
        print(f'Worker audio : {exc}', file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
