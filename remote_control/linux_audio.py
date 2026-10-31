"""mpv/ALSA sur Linux : IPC privée héritée, sans serveur ni dépendance pip."""
import json
import select
import shutil
import socket
import subprocess
import tempfile
import time


class LinuxWavePlayer:
    def __init__(self, device='alsa/default'):
        if not device.startswith('alsa/') or any(c in device for c in '\r\n\0'):
            raise ValueError('La sortie Linux doit être un périphérique alsa/… de mpv.')
        self.device = device
        self.volume = 70
        self.volume_supported = True
        self.opened = False
        self.process = self.channel = None
        self.diagnostic = None
        self.buffer = b''
        self.request_id = 0
        self.status = 'stopped'
        self.loaded = False
        self.error = None
        self.path = None
        self.position_ms = self.duration_ms = 0

    def _event(self, message):
        if message.get('event') == 'file-loaded':
            self.loaded, self.status = True, 'playing'
        elif message.get('event') == 'end-file':
            if message.get('reason') == 'eof' and self.loaded:
                self.status = 'stopped'
                self.position_ms = self.duration_ms
            else:
                self.error = message.get('file_error') or message.get('error') or 'Lecture audio interrompue.'
        elif message.get('event') == 'shutdown':
            self.error = 'Le lecteur audio s’est fermé.'

    def _message(self, timeout):
        if b'\n' not in self.buffer:
            if not select.select([self.channel], [], [], max(0, timeout))[0]:
                return None
            data = self.channel.recv(65536)
            if not data:
                raise RuntimeError('Connexion au lecteur audio interrompue.')
            self.buffer += data
            if len(self.buffer) > 1024 * 1024:
                raise RuntimeError('Réponse audio trop volumineuse.')
            if b'\n' not in self.buffer:
                return None
        line, self.buffer = self.buffer.split(b'\n', 1)
        message = json.loads(line)
        self._event(message)
        return message

    def _check(self):
        if self.error:
            raise RuntimeError(str(self.error))

    def _command(self, *command, timeout=2):
        self.request_id += 1
        request_id = self.request_id
        self.channel.sendall(json.dumps({'command': command, 'request_id': request_id},
                                        ensure_ascii=False).encode() + b'\n')
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            message = self._message(deadline - time.monotonic())
            self._check()
            if message and message.get('request_id') == request_id:
                if message.get('error') != 'success':
                    raise RuntimeError(f"Commande audio refusée : {message.get('error')}")
                return message.get('data')
        raise RuntimeError(f'Le lecteur audio ne répond pas à {command[0]} après {timeout} secondes.')

    def _failure_details(self, error):
        details = ''
        if self.diagnostic:
            self.diagnostic.seek(0, 2)
            length = self.diagnostic.tell()
            self.diagnostic.seek(max(0, length - 3000))
            details = self.diagnostic.read().decode('utf-8', errors='replace').strip()
        code = self.process.poll() if self.process else None
        return RuntimeError(f'{error}' + (f' (mpv : code {code})' if code is not None else '')
                            + (f'\nDiagnostic mpv :\n{details}' if details else ''))

    def start(self, path):
        self.close()
        executable = shutil.which('mpv')
        if not executable:
            raise RuntimeError('Installer mpv sur le Raspberry Pi pour lire les WAV.')
        self.error = None
        self.loaded = False
        self.position_ms = self.duration_ms = 0
        self.path = path
        parent, child = socket.socketpair()
        try:
            self.diagnostic = tempfile.TemporaryFile()
            # Le descripteur n'est accessible qu'au service et à son enfant mpv.
            # Aucune socket de commande n'est exposée sur le réseau/fichiers.
            self.process = subprocess.Popen([
                executable, '--no-config', '--load-scripts=no', '--ytdl=no',
                '--no-video', '--terminal=yes', '--msg-level=all=warn', '--idle=yes', '--keep-open=no',
                '--input-terminal=no', '--input-default-bindings=no',
                f'--input-ipc-client=fd://{child.fileno()}', f'--audio-device={self.device}',
                f'--volume={self.volume}', '--volume-max=100',
            ], pass_fds=(child.fileno(),), stdin=subprocess.DEVNULL,
                stdout=self.diagnostic, stderr=self.diagnostic)
            self.channel = parent
            parent.settimeout(2)
        except BaseException:
            parent.close()
            self.close()
            raise
        finally:
            child.close()
        self.opened = True
        try:
            # Sur un Zero 2 W à froid, le chargement de mpv et de ses bibliothèques
            # peut dépasser les deux secondes des commandes ordinaires. Attendre
            # sa disponibilité avant de demander le chargement du premier WAV.
            self._command('get_property', 'mpv-version', timeout=8)
            self._command('loadfile', str(path), 'replace')
            deadline = time.monotonic() + 4
            while not self.loaded and time.monotonic() < deadline:
                self._message(deadline - time.monotonic())
                self._check()
            if not self.loaded:
                raise RuntimeError('Le WAV n’a pas pu démarrer sur la sortie audio.')
            self.duration_ms = round(self._command('get_property', 'duration') * 1000)
        except Exception as exc:
            failure = self._failure_details(exc)
            self.close()
            raise failure from exc
        except BaseException:
            self.close()
            raise

    def mode(self):
        while self._message(0) is not None:
            pass
        self._check()
        if self.process.poll() is not None:
            raise RuntimeError('Le lecteur audio s’est arrêté de façon inattendue.')
        return self.status

    def pause(self):
        self._command('set_property', 'pause', True)
        self.status = 'paused'

    def resume(self):
        self._command('set_property', 'pause', False)
        self.status = 'playing'

    def replay(self):
        self.start(self.path)

    def set_volume(self, value):
        if self.opened:
            self._command('set_property', 'volume', value)
        self.volume = value
        return True

    def progress(self):
        if not self.opened:
            return None
        if self.mode() != 'stopped':
            try:
                self.position_ms = round(self._command('get_property', 'playback-time') * 1000)
            except RuntimeError:
                # L'événement EOF peut arriver entre mode() et get_property.
                if self.mode() != 'stopped':
                    raise
        return {'position_ms': max(0, min(self.position_ms, self.duration_ms)),
                'duration_ms': max(0, self.duration_ms)}

    def close(self):
        if self.channel:
            self.channel.close()
            self.channel = None
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=2)
            self.process = None
        self.buffer = b''
        self.opened = False
        if self.diagnostic:
            self.diagnostic.close()
            self.diagnostic = None
