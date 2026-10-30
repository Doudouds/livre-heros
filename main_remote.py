"""Télécommande téléphone, son joué localement par ce PC."""
import argparse
import sys
import webbrowser

from engine.content import Content, ROOT
from remote_control.audio import RemoteAudioPlayer
from remote_control.controller import PlaybackController, PlaybackService
from remote_control.server import RemoteServer, local_addresses


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--host', default='0.0.0.0', help='0.0.0.0 : réseau local ; 127.0.0.1 : ce PC seulement')
    result.add_argument('--port', type=int, default=8765)
    result.add_argument('--open', action='store_true', help='Ouvrir aussi la télécommande sur ce PC')
    result.add_argument('--no-restore', action='store_true', help='Commencer sans reprendre la dernière session')
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser().error('Le port doit être compris entre 1 et 65535.')
    service = None
    server = None
    try:
        content = Content()
        session = ROOT / 'sessions/remote/session.json'
        service = PlaybackService(lambda: PlaybackController(
            content, audio=RemoteAudioPlayer(content.root, content.config['audio_root']),
            session_path=session, restore=not args.no_restore))
        server = RemoteServer((args.host, args.port), service)
        print('\nLes Portes de l’Imaginaire — Télécommande téléphone', flush=True)
        print('Le son est joué par ce PC. Téléphone et PC doivent partager le même Wi-Fi.', flush=True)
        addresses = local_addresses() if args.host == '0.0.0.0' else [args.host]
        for address in addresses:
            label = 'Sur ce PC ' if address == '127.0.0.1' else 'Téléphone '
            print(f'{label}: http://{address}:{server.server_port}/#connexion={server.token}', flush=True)
            if address != '127.0.0.1':
                print(f'Application Android : http://{address}:{server.server_port}/android', flush=True)
        print('\nOuvre le lien Téléphone ou saisis le code dans la page de connexion.', flush=True)
        print(f'Code : {server.pair_code[:4]} {server.pair_code[4:]}', flush=True)
        print('Autorise Python sur le réseau privé si Windows le demande.', flush=True)
        print('Garde cette fenêtre ouverte. Ctrl+C arrête le service et le son.\n', flush=True)
        if args.open:
            webbrowser.open(f'http://127.0.0.1:{server.server_port}/#connexion={server.token}')
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        print('\nTélécommande arrêtée.', flush=True)
    except (OSError, ValueError) as exc:
        print(f'Impossible de démarrer la télécommande : {exc}', file=sys.stderr)
        return 1
    finally:
        if server:
            server.server_close()
        if service:
            service.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
