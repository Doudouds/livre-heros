"""Diagnostic sans synthèse et sans toucher à la session du lecteur."""
import argparse
import json
from pathlib import Path
import tempfile
import time
import wave

from engine.content import Content
from remote_control.audio import RemoteAudioPlayer
from remote_control.controller import PlaybackController


def check(device):
    content = Content()
    books = PlaybackController(content, restore=False).library()['books']
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        path = root / 'audio/files/check.wav'
        path.parent.mkdir(parents=True)
        with wave.open(str(path), 'wb') as output:
            output.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            output.writeframes(b'\0\0' * 48000)
        player = RemoteAudioPlayer(root, device=device)
        player.lead_in_ms = 0
        try:
            if not player.set_volume(5) or not player.play('check'):
                raise RuntimeError(player.last_error or 'La sortie audio ne démarre pas.')
            if not player.pause():
                raise RuntimeError('Pause refusée.')
            first = player.progress()
            time.sleep(0.15)
            second = player.progress()
            if player.state != 'paused' or abs(first['position_ms'] - second['position_ms']) > 20:
                raise RuntimeError('La pause ne conserve pas la position.')
            if not player.resume() or not player.replay():
                raise RuntimeError('Reprise ou rejeu refusé.')
            deadline = time.monotonic() + 6
            while player.state == 'playing' and time.monotonic() < deadline:
                time.sleep(0.05)
            if player.state != 'ready':
                raise RuntimeError(player.last_error or 'Fin réelle du WAV non détectée.')
            return {'audio_device': device, 'audio_check': 'passed', 'books': books}
        finally:
            player.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio-device', default='alsa/default')
    args = parser.parse_args()
    print(json.dumps(check(args.audio_device), ensure_ascii=False))
