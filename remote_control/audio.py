"""WAV locaux Windows/Linux, progression réelle et volume de cette lecture."""
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
    def __init__(self, root, audio_root='audio/files', *, device='alsa/default'):
        super().__init__(root, audio_root)
        if sys.platform == 'win32':
            self.windows = RemoteWindowsWavePlayer()
        elif sys.platform.startswith('linux'):
            from .linux_audio import LinuxWavePlayer
            self.native_backend = LinuxWavePlayer(device)

    @property
    def backend(self):
        return self.windows or self.native_backend

    @property
    def volume(self):
        return self.backend.volume if self.backend else None

    @property
    def volume_supported(self):
        return bool(self.backend and self.backend.volume_supported)

    def set_volume(self, value):
        return bool(self.backend and self.backend.set_volume(value))

    def progress(self):
        if self.native_backend:
            try:
                return self.native_backend.progress()
            except AUDIO_ERRORS as exc:
                self.last_error = str(exc)
                self.stop()
                return None
        if not self.windows or not self.windows.opened:
            return None
        try:
            position = int(self.windows.command(f'status {self.windows.alias} position'))
            duration = int(self.windows.command(f'status {self.windows.alias} length'))
            return {'position_ms': max(0, position), 'duration_ms': max(0, duration)}
        except (ValueError, *AUDIO_ERRORS):
            return None
