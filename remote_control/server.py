"""Petit serveur de télécommande sur le réseau local, sans dépendance pip."""
import hmac
import ipaddress
import json
import secrets
import socket
import sys
import threading
import time
from concurrent.futures import TimeoutError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .controller import StaleCommand


STATIC = Path(__file__).parent / 'static'
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/style.css': ('style.css', 'text/css; charset=utf-8'),
          '/icon.svg': ('icon.svg', 'image/svg+xml')}


def local_addresses():
    addresses = {'127.0.0.1'}
    try:
        for entry in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM):
            address = entry[4][0]
            if not ipaddress.ip_address(address).is_link_local:
                addresses.add(address)
    except OSError:
        pass
    return sorted(addresses, key=lambda item: (item == '127.0.0.1', item))


class RemoteServer(ThreadingHTTPServer):
    daemon_threads = True

    def server_bind(self):
        if sys.platform == 'win32':
            # Windows autorise sinon deux serveurs SO_REUSEADDR sur le même port.
            self.allow_reuse_address = False
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def __init__(self, address, service, *, token=None):
        super().__init__(address, RemoteHandler)
        self.service = service
        self.token = token or secrets.token_urlsafe(24)
        self.pair_code = f'{secrets.randbelow(100000000):08d}'
        self.pair_attempts = {}
        self.pair_lock = threading.Lock()
        names = {'localhost', socket.gethostname().lower(), socket.getfqdn().lower(), *local_addresses()}
        if address[0] != '0.0.0.0':
            names.add(address[0].lower())
        self.hosts = {f'{name}:{self.server_port}' for name in names}


class RemoteHandler(BaseHTTPRequestHandler):
    server_version = 'StoryRemote/1'

    def log_message(self, format, *args):
        # Ne jamais journaliser URL, corps ou code de connexion.
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def send(self, status, data, content_type='application/json; charset=utf-8'):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; "
                         "img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def valid_host(self):
        if self.headers.get('Host', '').lower() not in self.server.hosts:
            self.send(403, {'error': 'Adresse du lecteur non autorisée.'})
            return False
        origin = self.headers.get('Origin')
        if origin and origin.lower() != 'http://' + self.headers['Host'].lower():
            self.send(403, {'error': 'Cette origine n’est pas autorisée.'})
            return False
        return True

    def authorized(self):
        candidate = self.headers.get('X-Remote-Token', '')
        if not hmac.compare_digest(candidate.encode(), self.server.token.encode()):
            self.send(401, {'error': 'Ouvre le lien de connexion affiché sur le PC.'})
            return False
        return True

    def do_GET(self):
        if not self.valid_host():
            return
        path = urlsplit(self.path).path
        if path in ASSETS:
            filename, content_type = ASSETS[path]
            self.send(200, (STATIC / filename).read_bytes(), content_type)
        elif path in ('/api/state', '/api/library'):
            if not self.authorized():
                return
            self.call('state' if path == '/api/state' else 'library')
        else:
            self.send(404, {'error': 'Page introuvable.'})

    def do_POST(self):
        if not self.valid_host():
            return
        if self.path not in ('/api/command', '/api/connect'):
            self.send(404, {'error': 'Commande introuvable.'})
            return
        if self.path == '/api/command' and not self.authorized():
            return
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            self.send(415, {'error': 'Une commande JSON est requise.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 4096 or self.headers.get('Transfer-Encoding'):
                self.send(413, {'error': 'Commande trop volumineuse ou vide.'})
                return
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('Une commande doit être un objet JSON.')
        except (ValueError, UnicodeError):
            self.send(400, {'error': 'Commande JSON incorrecte.'})
            return
        if self.path == '/api/connect':
            self.connect(payload)
        else:
            self.call('command', payload)

    def connect(self, payload):
        now = time.monotonic()
        with self.server.pair_lock:
            self.server.pair_attempts = {key: value for key, value in self.server.pair_attempts.items()
                                         if now - value[0] < 60}
            key = self.client_address[0]
            since, attempts = self.server.pair_attempts.get(key, (now, 0))
            if attempts >= 10 or len(self.server.pair_attempts) > 256:
                self.send(429, {'error': 'Trop d’essais de connexion. Patientez une minute.'})
                return
            self.server.pair_attempts[key] = (since, attempts + 1)
        code = payload.get('code')
        if not isinstance(code, str) or not hmac.compare_digest(code.encode(), self.server.pair_code.encode()):
            self.send(401, {'error': 'Code incorrect. Utilisez les huit chiffres affichés sur le PC.'})
            return
        self.send(200, {'token': self.server.token})

    def call(self, operation, payload=None):
        try:
            self.send(200, self.server.service.request(operation, payload))
        except StaleCommand as exc:
            self.send(409, {'error': str(exc)})
        except (ValueError, KeyError, TypeError) as error:
            # Les messages métier ne contiennent ni chemins locaux ni secrets.
            self.send(400, {'error': str(error) if isinstance(error, ValueError) else 'Paramètre de commande incorrect.'})
        except TimeoutError:
            self.send(503, {'error': 'Le lecteur est occupé. Reconnexion en cours.'})
        except Exception:
            self.send(500, {'error': 'Le lecteur a rencontré une erreur. Actualise son état.'})

    def do_OPTIONS(self):
        self.send(403, {'error': 'Accès local uniquement.'})
