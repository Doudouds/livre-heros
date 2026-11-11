"""Installation Raspberry Pi OS, exécutée par l'utilisateur dans sa session SSH."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile


SERVICE = 'portes-imaginaire.service'
MARKER = '# Managed by Les Portes de l Imaginaire installer'


def run(*args, capture=False):
    return subprocess.run(args, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def usb_device(proc=Path('/proc/asound'), sound=Path('/sys/class/sound')):
    devices = []
    for card in sorted(proc.glob('card[0-9]*')):
        is_usb = (card / 'usbbus').exists() or 'usb' in str((sound / card.name / 'device').resolve())
        if not is_usb:
            continue
        identifier = (card / 'id').read_text().strip()
        playback = sorted(card.glob('pcm*p'))
        if playback and re.fullmatch(r'[A-Za-z0-9_-]+', identifier):
            device = playback[0].name[3:-1]
            devices.append(f'alsa/plughw:CARD={identifier},DEV={device}')
    if len(devices) != 1:
        raise ValueError('Une seule carte de sortie USB doit être branchée, ou préciser --audio-device. '
                         f'Sorties USB trouvées : {devices}')
    return devices[0]


def unpack(bundle, target):
    with zipfile.ZipFile(bundle) as archive:
        manifest = json.loads(archive.read('reader-manifest.json'))
        files = manifest['files']
        if manifest['format'] != 1 or len(files) != len(set(archive.namelist()) - {'reader-manifest.json'}):
            raise ValueError('Manifeste de lecture incorrect.')
        for name, digest in files.items():
            parts = PurePosixPath(name)
            if parts.is_absolute() or '..' in parts.parts or '\\' in name or not parts.parts:
                raise ValueError('Chemin de paquet incorrect.')
            path = target.joinpath(*parts.parts)
            if not path.resolve().is_relative_to(target.resolve()):
                raise ValueError('Chemin de paquet hors du lecteur.')
            path.parent.mkdir(parents=True, exist_ok=True)
            actual = hashlib.sha256()
            with archive.open(name) as source, path.open('wb') as destination:
                while block := source.read(1024 * 1024):
                    actual.update(block)
                    destination.write(block)
            if actual.hexdigest() != digest:
                raise ValueError(f'Empreinte incorrecte : {name}')


def service_text(root, user, device, port):
    # Ces valeurs entrent dans une unité systemd, jamais dans un shell.
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', str(root)) or not re.fullmatch(r'[A-Za-z0-9_-]+', user):
        raise ValueError('Chemin utilisateur non pris en charge par cet installateur.')
    if not re.fullmatch(r'alsa/[A-Za-z0-9_/:=,.-]+', device):
        raise ValueError('Nom de périphérique ALSA incorrect.')
    return f'''{MARKER}
[Unit]
Description=Les Portes de l Imaginaire - lecteur local
Wants=network-online.target
After=network-online.target sound.target

[Service]
Type=simple
User={user}
SupplementaryGroups=audio
WorkingDirectory={root}/current
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 -u {root}/current/main_remote.py --port {port} --audio-device {device} --no-code
Restart=on-failure
RestartSec=3
TimeoutStopSec=10
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths={root}/sessions {root}/tmp

[Install]
WantedBy=multi-user.target
'''


def install(args):
    if sys.version_info < (3, 10) or platform.system() != 'Linux':
        raise ValueError('Raspberry Pi OS avec Python 3.10 ou plus récent est requis.')
    if os.geteuid() == 0:
        raise ValueError('Lancer cette commande avec le compte SSH habituel, sans sudo devant python3.')
    import pwd
    user = pwd.getpwuid(os.getuid()).pw_name
    root = (Path.home() / '.local/share/portes-imaginaire').resolve()
    if root.exists() and not (root / 'installation.json').is_file():
        raise ValueError(f'{root} existe déjà sans marqueur ; aucun fichier n’a été remplacé.')
    unit_path = f'/etc/systemd/system/{SERVICE}'
    print('Vérification sudo et installation de Python, mpv et ALSA…', flush=True)
    run('sudo', '-v')
    exists = subprocess.run(['sudo', 'test', '-e', unit_path]).returncode == 0
    if exists and MARKER not in run('sudo', 'cat', unit_path, capture=True):
        raise ValueError('Une unité de ce nom existe déjà ; elle n’a pas été remplacée.')
    run('sudo', 'apt-get', 'update')
    run('sudo', 'apt-get', 'install', '-y', '--no-install-recommends', 'python3', 'mpv', 'alsa-utils')
    device = args.audio_device or usb_device()
    unit = service_text(root, user, device, args.port)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    (root / 'installation.json').write_text(json.dumps({'format': 1, 'user': user}))
    for name in ('releases', 'sessions', 'tmp'):
        (root / name).mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='install-', dir=root / 'tmp') as folder:
        folder = Path(folder)
        bundle = folder / 'reader.zip'
        print('Transfert des contes et vérification SHA-256…', flush=True)
        digest = hashlib.sha256()
        with urllib.request.urlopen(args.bundle, timeout=60) as response, bundle.open('wb') as output:
            while block := response.read(1024 * 1024):
                digest.update(block)
                output.write(block)
        if digest.hexdigest() != args.sha256:
            raise ValueError('L’empreinte du paquet transféré est incorrecte.')
        staged = folder / 'release'
        staged.mkdir()
        unpack(bundle, staged)
        for name in ('sessions', 'tmp'):
            (staged / name).symlink_to(root / name, target_is_directory=True)
        print(f'Contrôle réel de la sortie USB : {device} (WAV silencieux)…', flush=True)
        checked = subprocess.run(
            ['sudo', '-u', user, '-g', 'audio', '/usr/bin/python3', '-m',
             'tools.check_reader', '--audio-device', device], cwd=staged, text=True, capture_output=True)
        if checked.returncode:
            raise RuntimeError('Le contrôle audio a échoué :\n' + checked.stderr[-6000:])
        report = json.loads(checked.stdout)
        release = root / 'releases' / args.sha256[:20]
        if not release.exists():
            staged.rename(release)
        link = root / 'current.partial'
        link.unlink(missing_ok=True)
        link.symlink_to(release, target_is_directory=True)
        link.replace(root / 'current')
        (folder / SERVICE).write_text(unit)
        run('sudo', 'install', '-m', '644', str(folder / SERVICE), unit_path)
        run('sudo', 'systemctl', 'daemon-reload')
        run('sudo', 'systemctl', 'enable', SERVICE)
        run('sudo', 'systemctl', 'restart', SERVICE)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/api/state', timeout=2) as response:
                state = json.load(response)
                if response.status == 200 and isinstance(state, dict) and 'revision' in state:
                    report.update(hostname=platform.node(), port=args.port,
                                  status='installed', root=str(root))
                    print('\nLecteur actif. Dans Android, sélectionnez-le sur le Wi-Fi : aucun code requis.', flush=True)
                    print(f'Service : sudo systemctl status {SERVICE}', flush=True)
                    return report
        except (OSError, ValueError):
            pass
        time.sleep(0.25)
    raise RuntimeError(f'Le service ne répond pas. Consulter : sudo journalctl -u {SERVICE} -n 40')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--report-url')
    parser.add_argument('--audio-device')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not re.fullmatch('[a-f0-9]{64}', args.sha256):
        parser.error('Port ou empreinte incorrects.')
    report = {'status': 'failed'}
    try:
        report = install(args)
    except Exception as exc:
        report['error'] = str(exc)
        print(f'Installation interrompue : {exc}', file=sys.stderr, flush=True)
    finally:
        if args.report_url:
            try:
                request = urllib.request.Request(args.report_url, json.dumps(report).encode(),
                                                 {'Content-Type': 'application/json'}, method='POST')
                urllib.request.urlopen(request, timeout=5).close()
            except OSError:
                pass
    return 0 if report['status'] == 'installed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
