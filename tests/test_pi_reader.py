import hashlib
import json
from pathlib import Path, PurePosixPath
import socket
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch
import zipfile

from audio.audio_player import LocalAudioPlayer
from engine.content import ROOT
from remote_control.linux_audio import LinuxWavePlayer
from tools.install_reader import service_text, unpack, usb_device
from tools.package_reader import runtime_files
from tools.serve_reader_install import bootstrap
from main_remote import main


class FakeMpv:
    def __init__(self, connection, startup_delay=0):
        self.channel = connection
        self.finished = False
        self.commands = []
        self.properties = {'duration': 2, 'playback-time': 0.125, 'pause': False, 'volume': 70,
                           'mpv-version': 'mpv 0.40.0'}
        self.startup_delay = startup_delay
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def send(self, message):
        self.channel.sendall(json.dumps(message).encode() + b'\n')

    def run(self):
        threading.Event().wait(self.startup_delay)
        buffer = b''
        try:
            while data := self.channel.recv(65536):
                buffer += data
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    payload = json.loads(line)
                    command = payload['command']
                    self.commands.append(command)
                    reply = {'error': 'success', 'request_id': payload['request_id']}
                    if command[0] == 'loadfile':
                        self.send({'event': 'file-loaded'})
                    elif command[0] == 'get_property':
                        if command[1] in self.properties:
                            reply['data'] = self.properties[command[1]]
                        else:
                            reply['error'] = 'property unavailable'
                    elif command[0] == 'set_property':
                        self.properties[command[1]] = command[2]
                    self.send(reply)
        except OSError:
            pass

    def poll(self):
        return 0 if self.finished else None

    def terminate(self):
        self.finished = True
        self.channel.close()

    kill = terminate

    def wait(self, timeout=None):
        self.thread.join(timeout=timeout)
        return 0


class LinuxAudioTests(unittest.TestCase):
    def setUp(self):
        self.player = LinuxWavePlayer('alsa/plughw:CARD=USB,DEV=0')
        self.processes = []
        self.startup_delay = 0
        self.startup_error = None
        original_pair = socket.socketpair

        def pair():
            parent, child = original_pair()
            self.child = child
            return parent, child

        def popen(args, **kwargs):
            self.assertEqual(kwargs['pass_fds'], (self.child.fileno(),))
            self.assertIn(f'--input-ipc-client=fd://{self.child.fileno()}', args)
            self.assertIn('--no-config', args)
            self.assertIn('--load-scripts=no', args)
            self.assertIn('--audio-device=alsa/plughw:CARD=USB,DEV=0', args)
            self.assertFalse(any('ipc-server' in arg for arg in args))
            process = FakeMpv(self.child.dup(), self.startup_delay)
            if self.startup_error:
                kwargs['stderr'].write(self.startup_error.encode())
                kwargs['stderr'].flush()
                process.properties.pop('mpv-version')
            self.processes.append(process)
            return process

        self.patches = [patch('remote_control.linux_audio.socket.socketpair', side_effect=pair),
                        patch('remote_control.linux_audio.shutil.which', return_value='/usr/bin/mpv'),
                        patch('remote_control.linux_audio.subprocess.Popen', side_effect=popen)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        self.player.close()
        for process in self.processes:
            process.terminate()
            process.wait(timeout=1)
        for item in reversed(self.patches):
            item.stop()

    def test_real_ipc_preserves_pause_volume_progress_and_eof(self):
        self.assertTrue(self.player.set_volume(20))
        self.player.start(PurePosixPath('/tmp/une histoire.wav'))
        process = self.processes[-1]
        self.assertEqual(process.commands[:2], [['get_property', 'mpv-version'],
                                             ['loadfile', '/tmp/une histoire.wav', 'replace']])
        self.assertEqual(self.player.mode(), 'playing')
        self.player.pause()
        self.assertEqual(self.player.mode(), 'paused')
        self.assertTrue(process.properties['pause'])
        self.assertEqual(self.player.progress(), {'position_ms': 125, 'duration_ms': 2000})
        self.player.set_volume(35)
        self.assertEqual(process.properties['volume'], 35)
        self.player.resume()
        self.assertFalse(process.properties['pause'])
        process.send({'event': 'end-file', 'reason': 'eof'})
        self.assertEqual(self.player.mode(), 'stopped')
        self.assertEqual(self.player.progress()['position_ms'], 2000)
        self.player.replay()
        self.assertTrue(process.finished)
        self.assertEqual(len(self.processes), 2)
        self.assertEqual(self.player.mode(), 'playing')

    def test_device_failure_never_reports_natural_end(self):
        self.player.start(Path('/tmp/test.wav'))
        self.processes[-1].send({'event': 'end-file', 'reason': 'error', 'file_error': 'audio output failed'})
        with self.assertRaisesRegex(RuntimeError, 'audio output failed'):
            self.player.mode()

    def test_process_death_never_reports_natural_end(self):
        self.player.start(Path('/tmp/test.wav'))
        self.processes[-1].finished = True
        with self.assertRaisesRegex(RuntimeError, 'inattendue'):
            self.player.mode()

    def test_native_adapter_failure_stops_local_player(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'segment.wav').write_bytes(b'placeholder')
            player = LocalAudioPlayer(root, lead_in_ms=0)
            player.native_backend = self.player
            self.assertTrue(player.play('segment', 'segment.wav'))
            self.processes[-1].send({'event': 'end-file', 'reason': 'error', 'file_error': 'USB removed'})
            self.assertEqual(player.state, 'unavailable')
            self.assertIn('USB removed', player.last_error)
            self.assertFalse(self.player.opened)
            self.assertTrue(self.processes[-1].finished)

    def test_missing_mpv_and_invalid_device_are_explicit(self):
        with patch('remote_control.linux_audio.shutil.which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'Installer mpv'):
                self.player.start(Path('/tmp/test.wav'))
        for device in ('auto', 'null', 'alsa/default\nignored'):
            with self.assertRaises(ValueError):
                LinuxWavePlayer(device)

    def test_cold_start_longer_than_two_seconds_is_ready_before_loading_wav(self):
        self.startup_delay = 2.2
        self.player.start(PurePosixPath('/tmp/test.wav'))
        self.assertEqual(self.player.mode(), 'playing')
        self.assertEqual(self.processes[-1].commands[0], ['get_property', 'mpv-version'])

    def test_startup_failure_keeps_mpv_diagnostic_and_closes_process_and_log(self):
        self.startup_error = 'ALSA: device open failed'
        with self.assertRaisesRegex(RuntimeError, 'ALSA: device open failed'):
            self.player.start(PurePosixPath('/tmp/test.wav'))
        self.assertIsNone(self.player.diagnostic)
        self.assertIsNone(self.player.process)
        self.assertTrue(self.processes[-1].finished)


class DeploymentTests(unittest.TestCase):
    def test_service_connection_file_contains_code_without_token_and_is_removed_on_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            connection = Path(folder) / 'connection.json'
            server = MagicMock(server_port=8765, pair_code='12345678', token='private-token')
            def running(**kwargs):
                data = json.loads(connection.read_text())
                self.assertEqual(data['code'], '12345678')
                self.assertNotIn('token', data)
                raise KeyboardInterrupt
            server.serve_forever.side_effect = running
            with patch('main_remote.Content'), patch('main_remote.PlaybackService'), \
                    patch('main_remote.RemoteServer', return_value=server), \
                    patch('main_remote.local_addresses', return_value=['127.0.0.1']), \
                    patch('builtins.print'):
                self.assertEqual(main(['--connection-file', str(connection), '--no-discovery']), 0)
            self.assertFalse(connection.exists())

    def test_failed_launcher_does_not_remove_another_service_connection_file(self):
        with tempfile.TemporaryDirectory() as folder:
            connection = Path(folder) / 'connection.json'
            connection.write_text('existing')
            with patch('main_remote.Content'), patch('main_remote.PlaybackService'), \
                    patch('main_remote.RemoteServer', side_effect=OSError('port busy')), patch('builtins.print'):
                self.assertEqual(main(['--connection-file', str(connection)]), 1)
            self.assertEqual(connection.read_text(), 'existing')

    def test_runtime_contains_both_modes_and_receipts_but_no_models_secrets_or_admin(self):
        names = runtime_files()
        self.assertIn('remote_control/linux_audio.py', names)
        self.assertIn('tools/check_reader.py', names)
        for name in names:
            self.assertFalse(any(part in name for part in ('build_cache', 'chatterbox', '.env',
                              'Recording.wav', 'sessions/', 'audio_admin', 'content/authored')))
            if name.endswith('.wav') and (ROOT / (name + '.json')).is_file():
                self.assertIn(name + '.json', names)
        # Le contenu source permet ces deux rôles même dans un clone sans WAV.
        self.assertIn('content/books/roi_grenouille.json', names)

    def test_usb_card_uses_stable_identifier_and_playback_device(self):
        with tempfile.TemporaryDirectory() as folder:
            proc = Path(folder)
            card = proc / 'card2'
            card.mkdir()
            (card / 'usbbus').write_text('001/003')
            (card / 'id').write_text('USBCard\n')
            (card / 'pcm1p').mkdir()
            self.assertEqual(usb_device(proc, proc / 'sys'), 'alsa/plughw:CARD=USBCard,DEV=1')
            (card / 'usbbus').unlink()
            with self.assertRaisesRegex(ValueError, 'Une seule'):
                usb_device(proc, proc / 'sys')

    def test_unit_runs_without_root_and_keeps_only_sessions_and_cache_writable(self):
        unit = service_text(PurePosixPath('/home/edouard/.local/share/portes-imaginaire'), 'edouard',
                            'alsa/plughw:CARD=USB,DEV=0', 8765)
        self.assertIn('User=edouard', unit)
        self.assertIn('SupplementaryGroups=audio', unit)
        self.assertIn('ProtectHome=read-only', unit)
        self.assertIn('WantedBy=multi-user.target', unit)
        self.assertIn('--no-code', unit)
        self.assertNotIn('--connection-file', unit)
        with self.assertRaises(ValueError):
            service_text(PurePosixPath('/home/name with space'), 'user', 'alsa/default', 8765)

    def test_unpack_verifies_hashes_and_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / 'reader.zip'
            def write(name, digest=None):
                with zipfile.ZipFile(archive, 'w') as output:
                    output.writestr(name, b'source')
                    output.writestr('reader-manifest.json', json.dumps({'format': 1, 'files': {
                        name: digest or hashlib.sha256(b'source').hexdigest()}}))
            write('engine/content.py')
            unpack(archive, root / 'good')
            self.assertEqual((root / 'good/engine/content.py').read_bytes(), b'source')
            write('../escaped.py')
            with self.assertRaises(ValueError):
                unpack(archive, root / 'bad')
            self.assertFalse((root / 'escaped.py').exists())
            write('engine/content.py', '0' * 64)
            with self.assertRaisesRegex(ValueError, 'Empreinte'):
                unpack(archive, root / 'hash')

    def test_bootstrap_uses_argument_array_and_downloads_only_installer(self):
        script = bootstrap('http://192.168.1.220:8766/nonce', 'f' * 64).decode()
        compile(script, 'bootstrap', 'exec')
        self.assertIn('subprocess.call([', script)
        self.assertNotIn('shell=True', script)
        self.assertIn('--sha256', script)


if __name__ == '__main__':
    unittest.main()
