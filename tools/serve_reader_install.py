"""Transfert temporaire du lecteur PC vers un Pi déjà connecté en SSH."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import secrets
import shutil
import time

from engine.content import ROOT
from tools.package_reader import package


def bootstrap(base, digest):
    return f'''import pathlib, subprocess, sys, tempfile, urllib.request
with tempfile.TemporaryDirectory(prefix="portes-install-") as folder:
    script = pathlib.Path(folder) / "install.py"
    script.write_bytes(urllib.request.urlopen({base + '/install.py'!r}, timeout=20).read())
    result = subprocess.call([sys.executable, str(script), "--bundle", {base + '/reader.zip'!r},
                              "--sha256", {digest!r}, "--report-url", {base + '/report'!r}])
    if result:
        raise SystemExit(result)
'''.encode()


def serve(host, target, port=8766, duration=1800):
    info = package(ROOT / 'dist/raspberry/reader.zip')
    secret = secrets.token_urlsafe(24)
    report_path = ROOT / 'dist/raspberry/install-report.json'
    report_path.unlink(missing_ok=True)
    state = {'installed': False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def setup(self):
            super().setup()
            self.connection.settimeout(30)

        def send(self, status, data):
            self.send_response(status)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def allowed(self):
            return self.client_address[0] in (target, host, '127.0.0.1')

        def do_GET(self):
            if not self.allowed():
                return self.send(403, b'Forbidden')
            if self.path == f'/{secret}/bootstrap':
                return self.send(200, bootstrap(base, info['sha256']))
            if self.path == f'/{secret}/install.py':
                return self.send(200, (ROOT / 'tools/install_reader.py').read_bytes())
            if self.path != f'/{secret}/reader.zip':
                return self.send(404, b'Not found')
            with Path(info['archive']).open('rb') as source:
                self.send_response(200)
                self.send_header('Content-Type', 'application/zip')
                self.send_header('Content-Length', str(info['bytes']))
                self.end_headers()
                shutil.copyfileobj(source, self.wfile)

        def do_POST(self):
            if not self.allowed() or self.path != f'/{secret}/report':
                return self.send(403, b'Forbidden')
            try:
                size = int(self.headers.get('Content-Length', 0))
                if not 0 < size <= 16384:
                    raise ValueError('Size')
                report = json.loads(self.rfile.read(size))
                if not isinstance(report, dict) or report.get('status') not in ('installed', 'failed'):
                    raise ValueError('Report')
            except (ValueError, UnicodeError):
                return self.send(400, b'Invalid report')
            temporary = report_path.with_suffix('.partial')
            temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(report_path)
            state['installed'] = report['status'] == 'installed'
            print(f"Rapport du Pi : {report['status']} — {report.get('error', 'contrôles réussis')}", flush=True)
            self.send(200, b'OK')

    with HTTPServer((host, port), Handler) as server:
        base = f'http://{host}:{server.server_port}/{secret}'
        command = f'python3 -c "import urllib.request; exec(urllib.request.urlopen(\'{base}/bootstrap\').read())"'
        print(json.dumps({'command': command, 'target': target, 'sha256': info['sha256'],
                          'bytes': info['bytes'], 'expires_in_seconds': duration}, ensure_ascii=False), flush=True)
        server.timeout = 1
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline and not state['installed']:
            try:
                server.handle_request()
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass
    print('Transfert temporaire fermé.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True, help='Adresse locale du PC')
    parser.add_argument('--target', required=True, help='Adresse locale du Pi autorisé')
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    serve(args.host, args.target, args.port)
