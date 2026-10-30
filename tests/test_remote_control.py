import copy
import http.client
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from engine.book_engine import BookEngine
from engine.content import Content, ROOT
from remote_control.audio import RemoteAudioPlayer, RemoteWindowsWavePlayer
from remote_control.controller import PlaybackController, PlaybackService, StaleCommand, book_segments
from remote_control.server import RemoteServer


def write_wave(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as handle:
        handle.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
        handle.writeframes(b'\0\0' * 2400)


class FakeAudio:
    volume_supported = True
    volume = 70

    def __init__(self, root, audio_root):
        self.root, self.audio_root = Path(root), Path(root) / audio_root
        self._state = 'unavailable'
        self.calls = []
        self.threads = set()
        self.last = None

    @property
    def state(self):
        self.threads.add(threading.get_ident())
        return self._state

    def play(self, segment_id, audio_file=None):
        self.threads.add(threading.get_ident())
        path = self.audio_root / (segment_id + '.wav')
        if not path.is_file() and audio_file:
            path = self.root / audio_file
        self.last = path
        self.calls.append(('play', segment_id, self.lead_in_ms))
        self._state = 'playing' if path.is_file() else 'unavailable'
        return self._state == 'playing'

    def pause(self):
        if self.state != 'playing':
            return False
        self._state = 'paused'
        return True

    def resume(self):
        if self.state not in ('paused', 'ready'):
            return False
        self._state = 'playing'
        return True

    def stop(self):
        self.threads.add(threading.get_ident())
        self._state = 'unavailable'

    def set_volume(self, volume):
        self.volume = volume
        return True

    def progress(self):
        return {'position_ms': 100, 'duration_ms': 1000} if self._state != 'unavailable' else None


class PlaybackFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / 'tmp')
        self.folder = Path(self.temporary.name)
        self.content = Content()
        self.content.config = copy.deepcopy(self.content.config)
        self.content.config['audio_root'] = (self.folder / 'legacy').relative_to(ROOT).as_posix()
        self.content.config['book_audio_roots'] = {
            key: (self.folder / key).relative_to(ROOT).as_posix() for key in self.content.books}
        self.audio = FakeAudio(ROOT, self.content.config['audio_root'])
        self.controller = PlaybackController(self.content, audio=self.audio)

    def tearDown(self):
        self.temporary.cleanup()

    def prepare(self, automatic=True):
        paths = []
        for scene in book_segments(self.content, 'roi_grenouille', automatic):
            path = ROOT / self.content.config['book_audio_roots']['roi_grenouille'] / (scene['segment_id'] + '.wav')
            write_wave(path)
            paths.append(path)
        return paths

    def send(self, action, **kwargs):
        return self.controller.command({'revision': self.controller.revision, 'action': action, **kwargs})

    def start(self, mode='automatic'):
        return self.send('start', kind='book', id='roi_grenouille', mode=mode)


class PlaybackTests(PlaybackFixture):
    def test_catalog_distinguishes_both_complete_plans_without_importing_tts(self):
        self.assertEqual(len(self.prepare(True)), 11)
        self.assertEqual(len(self.prepare(False)), 21)
        with patch.dict(sys.modules, {'torch': None, 'chatterbox': None, 'faster_whisper': None}):
            catalog = self.controller.library()
        book = next(b for b in catalog['books'] if b['id'] == 'roi_grenouille')
        self.assertEqual(book['modes']['automatic'], {'available': 11, 'total': 11, 'complete': True})
        self.assertEqual(book['modes']['interactive'], {'available': 21, 'total': 21, 'complete': True})

    def test_catalog_covers_mixed_choices_and_delayed_flags(self):
        known = {scene['segment_id'] for scene in book_segments(self.content, 'passeuse_ch1')}
        engine = BookEngine(self.content, 'passeuse_ch1')
        while True:
            self.assertIn(engine.current['segment_id'], known)
            if engine.finished:
                break
            engine.choose(engine.state.story_progress % 2)
            engine.advance()

    def test_automatic_waits_for_sound_and_pause_then_completes_once(self):
        paths = self.prepare()
        state = self.start()
        self.assertEqual(self.audio.last, paths[0])
        self.assertEqual(self.audio.calls[-1][2], 0)
        self.assertEqual(state['choices'], [])
        self.assertIsNone(state['question'])
        self.assertNotIn('Choix 1 :', state['text'])
        self.controller.tick()
        self.assertEqual(self.controller.engine.current['rank'], 1)
        self.send('pause')
        for _ in range(5):
            self.controller.tick()
        self.assertEqual(self.controller.engine.current['rank'], 1)
        self.send('resume')
        for rank in range(2, 12):
            self.audio._state = 'ready'
            self.controller.tick()
            self.assertEqual(self.controller.engine.current['rank'], rank)
        self.assertFalse(self.controller.snapshot()['completed'])
        self.audio._state = 'ready'
        self.controller.tick()
        self.assertTrue(self.controller.snapshot()['completed'])
        calls = list(self.audio.calls)
        self.controller.tick()
        self.assertEqual(self.audio.calls, calls)
        self.assertEqual([c['choice_index'] for c in self.controller.engine.journal['choices']], [0] * 10)

    def test_automatic_start_is_atomic_when_incomplete(self):
        self.start('interactive')
        previous = self.controller.engine
        with self.assertRaisesRegex(ValueError, '0/11'):
            self.start()
        self.assertIs(self.controller.engine, previous)

    def test_deleted_file_never_skips_or_uses_interactive_or_generic_wav(self):
        paths = self.prepare()
        self.prepare(False)
        self.start()
        paths[1].unlink()
        generic = ROOT / self.content.config['audio_root'] / paths[1].name
        write_wave(generic)
        self.audio._state = 'ready'
        self.controller.tick()
        self.assertEqual(self.controller.engine.current['rank'], 2)
        self.assertEqual(self.audio.state, 'unavailable')
        self.controller.tick()
        self.assertEqual(self.controller.engine.current['rank'], 2)
        self.assertIn('suspendue', self.controller.snapshot()['error'])
        write_wave(paths[1])
        self.send('resume')
        self.assertEqual(self.audio.last, paths[1])
        self.assertEqual(self.audio.state, 'playing')

    def test_replay_restart_and_stop_preserve_mode_and_position(self):
        self.prepare()
        self.start()
        self.audio._state = 'ready'
        self.controller.tick()
        segment = self.controller.engine.current['segment_id']
        self.send('stop')
        self.controller.tick()
        self.assertEqual(self.controller.engine.current['segment_id'], segment)
        self.send('replay')
        self.assertEqual(self.controller.engine.current['segment_id'], segment)
        self.assertTrue(self.controller.engine.automatic)
        self.send('restart')
        self.assertTrue(self.controller.engine.automatic)
        self.assertEqual(self.controller.engine.current['rank'], 1)

    def test_automatic_refuses_choices_and_manual_advance(self):
        self.prepare()
        self.start()
        with self.assertRaises(ValueError):
            self.send('choose', index=1)
        with self.assertRaises(ValueError):
            self.send('advance')
        self.assertEqual(self.controller.engine.current['rank'], 1)

    def test_interactive_choices_and_stale_double_tap(self):
        state = self.start('interactive')
        self.assertEqual(len(state['choices']), 2)
        old = state['revision']
        self.send('choose', index=1)
        with self.assertRaises(StaleCommand):
            self.controller.command({'action': 'choose', 'index': 1, 'revision': old})
        self.assertEqual(self.controller.engine.state.story_progress, 1)
        self.assertIn(self.controller.engine.book['scenes'][0]['choices'][1]['consequence'], self.controller.engine.current['text'])

    def test_old_adventures_keep_intro_and_separate_consequences(self):
        self.send('start', kind='adventure', id='lantern', hero='knight', location='forest',
                  item=next(iter(self.content.items)))
        self.assertTrue(self.controller.snapshot()['can_advance'])
        self.send('advance')
        state = self.send('choose', index=0)
        self.assertEqual(state['choices'], [])
        self.assertTrue(state['can_advance'])
        self.send('advance')
        self.assertEqual(len(self.controller.snapshot()['choices']), 2)

    def test_invalid_command_does_not_mutate_session(self):
        self.start('interactive')
        scene = self.controller.engine.current['id']
        for action, kwargs in [('choose', {'index': True}), ('volume', {'value': 101}), ('explode', {})]:
            with self.assertRaises(ValueError):
                self.send(action, **kwargs)
        self.assertEqual(self.controller.engine.current['id'], scene)

    def test_session_restores_choices_without_playing_sound(self):
        path = self.folder / 'session.json'
        self.controller.session_path = path
        self.prepare()
        self.start()
        self.audio._state = 'ready'
        self.controller.tick()
        fresh_audio = FakeAudio(ROOT, self.content.config['audio_root'])
        restored = PlaybackController(self.content, audio=fresh_audio, session_path=path)
        self.assertEqual(restored.engine.current, self.controller.engine.current)
        self.assertEqual(fresh_audio.calls, [])
        self.assertTrue(restored.snapshot()['stopped'])
        self.assertTrue(restored.engine.automatic)
        restored.command({'action': 'resume', 'revision': restored.revision})
        self.assertEqual(fresh_audio.state, 'playing')
        self.assertEqual(restored.engine.current['rank'], 2)
        self.assertFalse(path.with_suffix('.partial').exists())

    def test_corrupt_session_does_not_prevent_a_new_story(self):
        path = self.folder / 'session.json'
        path.write_text('{', encoding='utf-8')
        restored = PlaybackController(self.content, audio=self.audio, session_path=path)
        self.assertIsNone(restored.engine)
        self.assertIn('ancienne session', restored.error)

    def test_service_advances_without_http_clients_and_serializes_audio(self):
        self.prepare()
        audio = FakeAudio(ROOT, self.content.config['audio_root'])
        service = PlaybackService(lambda: PlaybackController(self.content, audio=audio), interval=0.01)
        try:
            service.request('command', {'action': 'start', 'kind': 'book', 'id': 'roi_grenouille',
                                        'mode': 'automatic', 'revision': 0})
            audio._state = 'ready'
            deadline = time.monotonic() + 2
            while len(audio.calls) < 2 and time.monotonic() < deadline:
                threading.Event().wait(0.01)
            self.assertEqual(len(audio.calls), 2)
            self.assertEqual(service.request('state')['passage'], 2)
            self.assertEqual(audio.threads, {service.thread.ident})
        finally:
            service.close()
        self.assertFalse(service.thread.is_alive())


class RemoteHTTPTests(PlaybackFixture):
    def setUp(self):
        super().setUp()
        self.service = PlaybackService(lambda: self.controller, interval=0.01)
        self.server = RemoteServer(('127.0.0.1', 0), self.service, token='test-session-token')
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.01})
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()
        self.service.close()
        super().tearDown()

    def request(self, path, payload=None, *, token=True, headers=None, raw=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        fields = {'X-Remote-Token': self.server.token} if token else {}
        if payload is not None or raw is not None:
            fields['Content-Type'] = 'application/json'
        fields.update(headers or {})
        body = json.dumps(payload) if payload is not None else raw
        connection.request('POST' if body is not None else 'GET', path, body=body, headers=fields)
        response = connection.getresponse()
        data = response.read()
        result = response.status, response.getheader('Content-Type'), data
        connection.close()
        return result

    def test_http_requires_current_connection_token(self):
        self.assertEqual(self.request('/api/state', token=False)[0], 401)
        self.assertEqual(self.request('/api/state', headers={'X-Remote-Token': 'old'})[0], 401)
        self.assertEqual(self.request('/api/state')[0], 200)
        status, _, data = self.request('/api/connect', {'code': self.server.pair_code}, token=False)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)['token'], self.server.token)

    def test_http_second_launcher_cannot_share_the_same_port(self):
        with self.assertRaises(OSError):
            RemoteServer(('127.0.0.1', self.server.server_port), self.service)

    def test_android_installer_serves_only_the_prepared_apk_without_credentials(self):
        self.assertEqual(self.request('/android', token=False)[0], 200)
        target = self.folder / 'test.apk'
        with patch('remote_control.server.ANDROID_APK', target):
            self.assertEqual(self.request('/android.apk', token=False)[0], 404)
            target.write_bytes(b'prepared-apk-without-credentials')
            status, mime, content = self.request('/android.apk', token=False)
            self.assertEqual(status, 200)
            self.assertEqual(mime, 'application/vnd.android.package-archive')
            self.assertEqual(content, target.read_bytes())
        self.assertEqual(self.request('/api/state', token=False)[0], 401)

    def test_http_pairing_throttles_wrong_codes(self):
        for _ in range(10):
            self.assertEqual(self.request('/api/connect', {'code': 'wrong'}, token=False)[0], 401)
        self.assertEqual(self.request('/api/connect', {'code': self.server.pair_code}, token=False)[0], 429)

    def test_http_rejects_foreign_origins_and_dns_rebinding(self):
        payload = {'action': 'start', 'kind': 'book', 'id': 'roi_grenouille', 'revision': 0}
        self.assertEqual(self.request('/api/command', payload, headers={'Origin': 'https://example.com'})[0], 403)
        self.assertEqual(self.request('/api/state', headers={'Host': 'attacker.example'})[0], 403)
        self.assertFalse(self.controller.engine)

    def test_http_serves_only_allowlisted_assets_and_no_audio_or_project_files(self):
        self.assertEqual(self.request('/', token=False)[0], 200)
        self.assertIn('text/javascript', self.request('/app.js', token=False)[1])
        for path in ('/../config.json', '/config.json', '/audio/files/test.wav', '/sessions/remote/session.json'):
            self.assertEqual(self.request(path)[0], 404)

    def test_http_bad_commands_are_bounded_and_leave_service_alive(self):
        self.assertEqual(self.request('/api/command', raw='{')[0], 400)
        self.assertEqual(self.request('/api/command', raw='x' * 4097)[0], 413)
        self.assertEqual(self.request('/api/command', [1])[0], 400)
        self.assertEqual(self.request('/api/command', {'revision': 0, 'action': 'start', 'kind': 'book', 'id': []})[0], 400)
        self.assertEqual(self.request('/api/state')[0], 200)

    def test_http_concurrent_choices_apply_once(self):
        status, _, data = self.request('/api/command', {'action': 'start', 'kind': 'book', 'id': 'roi_grenouille', 'revision': 0})
        self.assertEqual(status, 200)
        revision = json.loads(data)['revision']
        payload = {'action': 'choose', 'index': 0, 'revision': revision}
        with ThreadPoolExecutor(max_workers=2) as workers:
            statuses = list(workers.map(lambda _: self.request('/api/command', payload)[0], range(2)))
        self.assertEqual(sorted(statuses), [200, 409])
        self.assertEqual(self.controller.engine.state.story_progress, 1)


@unittest.skipUnless(sys.platform == 'win32', 'Adaptateur MCI Windows')
class RemoteAudioTests(unittest.TestCase):
    def test_digital_audio_uses_per_player_volume_and_millisecond_progress(self):
        player = RemoteWindowsWavePlayer()
        with patch.object(player, 'command', return_value='') as command:
            player.start(Path('story.wav'))
            self.assertIn('type mpegvideo', command.call_args_list[0].args[0])
            player.set_volume(25)
            self.assertIn('volume to 250', command.call_args.args[0])
            self.assertEqual(player.volume, 25)
            player.close()

    def test_waveaudio_fallback_does_not_claim_volume_control(self):
        player = RemoteWindowsWavePlayer()
        with patch.object(player, 'command', side_effect=[RuntimeError('no digitalvideo'), '', '', '']):
            player.start(Path('story.wav'))
        self.assertFalse(player.volume_supported)
        self.assertFalse(player.set_volume(20))


@unittest.skipUnless(sys.platform == 'win32' and os.environ.get('STORY_NATIVE_AUDIO') == '1',
                     'Vérification matérielle facultative avec un WAV silencieux')
class NativeRemoteAudioTests(unittest.TestCase):
    def test_real_pause_volume_progress_replay_and_natural_end(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as folder:
            root = Path(folder)
            target = root / 'audio/files/silence.wav'
            target.parent.mkdir(parents=True)
            with wave.open(str(target), 'wb') as handle:
                handle.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                handle.writeframes(b'\0\0' * 48000)
            player = RemoteAudioPlayer(root)
            player.lead_in_ms = 0
            try:
                self.assertTrue(player.play('silence'), player.last_error)
                self.assertTrue(player.volume_supported)
                self.assertTrue(player.set_volume(20))
                self.assertEqual(player.volume, 20)
                self.assertEqual(player.progress()['duration_ms'], 2000)
                self.assertTrue(player.pause())
                position = player.progress()['position_ms']
                threading.Event().wait(0.15)
                self.assertEqual(player.state, 'paused')
                self.assertEqual(player.progress()['position_ms'], position)
                self.assertTrue(player.resume())
                self.assertTrue(player.replay())
                deadline = time.monotonic() + 4
                while player.state == 'playing' and time.monotonic() < deadline:
                    threading.Event().wait(0.05)
                self.assertEqual(player.state, 'ready')
            finally:
                player.stop()


if __name__ == '__main__':
    unittest.main()
