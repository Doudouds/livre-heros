"""Télécommande téléphone, son joué localement sur PC ou Raspberry Pi."""
import argparse
import json
import os
from pathlib import Path
import signal
import sys
import threading
import webbrowser

from engine.content import Content, ROOT
from remote_control.audio import RemoteAudioPlayer
from remote_control.controller import PlaybackController, PlaybackService
from remote_control.discovery import DiscoveryResponder
from remote_control.server import RemoteServer, local_addresses


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--host', default='0.0.0.0', help='0.0.0.0 : réseau local ; 127.0.0.1 : ce PC seulement')
    result.add_argument('--port', type=int, default=8765)
    result.add_argument('--open', action='store_true', help='Ouvrir aussi la télécommande sur ce PC')
    result.add_argument('--no-restore', action='store_true', help='Commencer sans reprendre la dernière session')
    result.add_argument('--no-discovery', action='store_true', help='Désactiver la découverte locale depuis Android')
    result.add_argument('--audio-device', default='alsa/default', help='Sortie Linux mpv, par exemple alsa/plughw:CARD=Device,DEV=0')
    pairing = result.add_mutually_exclusive_group()
    pairing.add_argument('--no-code', action='store_true', help='Autoriser la télécommande sans code depuis les adresses locales')
    pairing.add_argument('--connection-file', type=Path, help='Fichier privé contenant le code courant')
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser().error('Le port doit être compris entre 1 et 65535.')
    service = None
    server = None
    discovery = None
    previous_signal = None
    connection_written = False
    try:
        if threading.current_thread() is threading.main_thread():
            def terminate(signum, frame):
                raise KeyboardInterrupt
            previous_signal = signal.signal(signal.SIGTERM, terminate)
        content = Content()
        session = ROOT / 'sessions/remote/session.json'
        service = PlaybackService(lambda: PlaybackController(
            content, audio=RemoteAudioPlayer(content.root, content.config['audio_root'], device=args.audio_device),
            session_path=session, restore=not args.no_restore))
        server = RemoteServer((args.host, args.port), service, no_code=args.no_code)
        if args.connection_file:
            args.connection_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = args.connection_file.with_suffix('.partial')
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump({'code': server.pair_code, 'port': server.server_port,
                           'pid': os.getpid()}, handle)
            temporary.replace(args.connection_file)
            connection_written = True
        if args.host == '0.0.0.0' and not args.no_discovery:
            try:
                discovery = DiscoveryResponder(server.server_port)
            except OSError:
                print('Découverte locale indisponible ; la connexion par adresse reste disponible.', flush=True)
        print('\nLes Portes de l’Imaginaire — Télécommande téléphone', flush=True)
        print('Le son est joué par ce lecteur. Téléphone et lecteur doivent partager le même réseau local.', flush=True)
        if discovery:
            print('Dans l’application Android : Rechercher un lecteur, puis sélectionner cet appareil.', flush=True)
        addresses = local_addresses() if args.host == '0.0.0.0' else [args.host]
        fragment = '' if args.no_code or args.connection_file else f'#connexion={server.token}'
        for address in addresses:
            label = 'Sur ce PC ' if address == '127.0.0.1' else 'Téléphone '
            print(f'{label}: http://{address}:{server.server_port}/{fragment}', flush=True)
            if address != '127.0.0.1':
                print(f'Application Android : http://{address}:{server.server_port}/android', flush=True)
        if args.no_code:
            print('\nAccès sans code depuis le réseau local.', flush=True)
        else:
            print('\nOuvre le lien Téléphone ou saisis le code dans la page de connexion.', flush=True)
            print(f'Code : {server.pair_code[:4]} {server.pair_code[4:]}', flush=True)
        if sys.platform == 'win32':
            print('Autorise Python sur le réseau privé si Windows le demande.', flush=True)
        print('Ctrl+C arrête le service et le son.\n', flush=True)
        if args.open:
            open_fragment = '' if args.no_code else f'#connexion={server.token}'
            webbrowser.open(f'http://127.0.0.1:{server.server_port}/{open_fragment}')
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        print('\nTélécommande arrêtée.', flush=True)
    except (OSError, ValueError) as exc:
        print(f'Impossible de démarrer la télécommande : {exc}', file=sys.stderr)
        return 1
    finally:
        if discovery:
            discovery.close()
        if server:
            server.server_close()
        if service:
            service.close()
        if connection_written:
            args.connection_file.unlink(missing_ok=True)
        if previous_signal is not None:
            signal.signal(signal.SIGTERM, previous_signal)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
