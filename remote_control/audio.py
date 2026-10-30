"""Adaptateur PC : WAV locaux, progression réelle et volume de cette lecture."""
import sys

from audio.audio_player import AUDIO_ERRORS, LocalAudioPlayer, WindowsWavePlayer


class RemoteWindowsWavePlayer(WindowsWavePlayer):
    def __init__(self):
        super().__init__()
        self.volume = 70
        self.volume_supported = True

    def start(self, path):
        # digitalvideo sait lire le PCM WAV et régler son volume indépendamment
        # du volume général de Windows ; waveaudio reste le repli sans volume.
        try:
            self.command(f'open "{path}" type mpegvideo alias {self.alias}')
            self.opened = True
            self.volume_supported = True
        except AUDIO_ERRORS:
            super().start(path)
            self.volume_supported = False
            return
        self.command(f'set {self.alias} time format milliseconds')
        self.set_volume(self.volume)
        self.command(f'play {self.alias}')

    def set_volume(self, value):
        if not self.volume_supported:
            return False
        if self.opened:
            try:
                self.command(f'setaudio {self.alias} volume to {value * 10}')
            except AUDIO_ERRORS:
                self.volume_supported = False
                return False
        self.volume = value
        return True


class RemoteAudioPlayer(LocalAudioPlayer):
    def __init__(self, root, audio_root='audio/files'):
        super().__init__(root, audio_root)
        if sys.platform == 'win32':
            self.windows = RemoteWindowsWavePlayer()

    @property
    def volume(self):
        return self.windows.volume if self.windows else None

    @property
    def volume_supported(self):
        return bool(self.windows and self.windows.volume_supported)

    def set_volume(self, value):
        return bool(self.windows and self.windows.set_volume(value))

    def progress(self):
        if not self.windows or not self.windows.opened:
            return None
        try:
            position = int(self.windows.command(f'status {self.windows.alias} position'))
            duration = int(self.windows.command(f'status {self.windows.alias} length'))
            return {'position_ms': max(0, position), 'duration_ms': max(0, duration)}
        except (ValueError, *AUDIO_ERRORS):
            return None
