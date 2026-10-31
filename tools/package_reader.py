"""Paquet de lecture Pi : code utile, contenu, WAV existants et reçus, sans TTS."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from engine.content import Content, ROOT
from remote_control.controller import PlaybackController, book_segments
from engine.book_engine import BookEngine


def runtime_files(root=ROOT):
    root = Path(root).resolve()
    names = {'main_remote.py', 'config.json', 'audio/__init__.py', 'audio/audio_player.py',
             'tools/__init__.py', 'tools/check_reader.py'}
    # Imports réels du lecteur : aucune administration, synthèse ou bibliothèque GUI.
    for filename in ('__init__', 'content', 'story_engine', 'book_engine', 'story_state',
                     'rules', 'probability'):
        names.add(f'engine/{filename}.py')
    names.update(p.relative_to(root).as_posix() for p in (root / 'remote_control').glob('*.py'))
    names.update(p.relative_to(root).as_posix() for p in (root / 'remote_control/static').glob('*') if p.is_file())
    for directory in ('content', 'content/arcs', 'content/scenes', 'content/books'):
        names.update(p.relative_to(root).as_posix() for p in (root / directory).glob('*.json'))
    content = Content(root)
    controller = PlaybackController(content, restore=False)
    # Seulement les WAV courants des livres, pas leurs anciennes prises/caches.
    for book_id, book in content.books.items():
        for automatic in (False, True) if book.get('audio_tagged_version') == 1 else (False,):
            engine = BookEngine(content, book_id, automatic=automatic)
            for scene in book_segments(content, book_id, automatic):
                path = controller.audio_path(engine, scene)
                if path:
                    names.add(path.relative_to(root).as_posix())
    # Les aventures historiques utilisent le répertoire générique.
    names.update(p.relative_to(root).as_posix() for p in (root / content.config['audio_root']).glob('*.wav'))
    for name in list(names):
        if name.endswith('.wav') and (root / (name + '.json')).is_file():
            names.add(name + '.json')
    apk = 'dist/android/LesPortesImaginaire.apk'
    if (root / apk).is_file():
        names.add(apk)
    for name in names:
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f'Fichier de lecture invalide : {name}')
    return sorted(names)


def package(target, root=ROOT):
    root, target = Path(root), Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.partial')
    manifest = {'format': 1, 'files': {}}
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
            for name in runtime_files(root):
                path = root / name
                before = path.stat()
                digest = hashlib.sha256()
                with path.open('rb') as source, archive.open(name, 'w') as destination:
                    while block := source.read(1024 * 1024):
                        digest.update(block)
                        destination.write(block)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError(f'Fichier modifié pendant le transfert : {name} ; relancer.')
                manifest['files'][name] = digest.hexdigest()
            archive.writestr('reader-manifest.json', json.dumps(manifest, ensure_ascii=False))
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    digest = hashlib.sha256()
    with target.open('rb') as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return {'archive': str(target), 'sha256': digest.hexdigest(), 'files': len(manifest['files']),
            'bytes': target.stat().st_size}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/raspberry/reader.zip')
    args = parser.parse_args()
    print(json.dumps(package(args.output), ensure_ascii=False))
