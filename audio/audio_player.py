"""Lecture locale facultative, avec pause et reprise, sans dépendance externe."""
import hashlib
import shutil
import signal
import subprocess
import sys
import tempfile
import uuid
import wave
from pathlib import Path
from typing import Protocol


class AudioPlayer(Protocol):
    @property
    def state(self) -> str:
        ...

    def play(self, segment_id: str, audio_file: str | None = None) -> bool:
        ...

    def pause(self) -> bool:
        ...

    def resume(self) -> bool:
        ...

    def replay(self) -> bool:
        ...

    def stop(self) -> None:
        ...


class SilentAudioPlayer:
    state = "unavailable"

    def play(self, segment_id, audio_file=None):
        return False

    def pause(self):
        return False

    def resume(self):
        return False

    def replay(self):
        return False

    def stop(self):
        pass


def wave_with_lead_in(source, milliseconds, cache_root):
    """Copie de lecture : vrai silence PCM pour laisser le périphérique démarrer.

    L'original et son reçu TTS restent intacts. Le cache se renouvelle si le
    fichier source ou la durée du silence change. Écriture atomique, par blocs.
    """
    if not milliseconds:
        return source
    stat = source.stat()
    identity = f"{source}|{stat.st_mtime_ns}|{stat.st_size}|{milliseconds}"
    target = cache_root / (hashlib.sha256(identity.encode("utf-8")).hexdigest() + ".wav")
    if target.is_file():
        return target
    cache_root.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with wave.open(str(source), "rb") as audio:
            if audio.getcomptype() != "NONE":
                raise ValueError("Le WAV doit contenir de l'audio PCM.")
            with tempfile.NamedTemporaryFile(dir=cache_root, suffix=".partial", delete=False) as handle:
                temporary = Path(handle.name)
                with wave.open(handle, "wb") as padded:
                    padded.setparams(audio.getparams())
                    # PCM 8 bits non signé : le silence est 128, pas zéro.
                    zero = b"\x80" if audio.getsampwidth() == 1 else b"\0" * audio.getsampwidth()
                    padded.writeframesraw(zero * audio.getnchannels() *
                                          (audio.getframerate() * milliseconds // 1000))
                    while block := audio.readframes(65536):
                        padded.writeframesraw(block)
        temporary.replace(target)
        return target
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class WindowsWavePlayer:
    """Commandes MCI Windows : pause conserve la position dans le WAV."""

    def __init__(self):
        import ctypes
        self.ctypes = ctypes
        self.library = ctypes.WinDLL("winmm")
        self.library.mciSendStringW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p,
                                               ctypes.c_uint, ctypes.c_void_p]
        self.library.mciSendStringW.restype = ctypes.c_uint
        self.library.mciGetErrorStringW.argtypes = [ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
        self.library.mciGetErrorStringW.restype = ctypes.c_int
        self.alias = "story_audio_" + uuid.uuid4().hex
        self.opened = False

    def command(self, command):
        output = self.ctypes.create_unicode_buffer(512)
        code = self.library.mciSendStringW(command, output, len(output), None)
        if code:
            error = self.ctypes.create_unicode_buffer(512)
            self.library.mciGetErrorStringW(code, error, len(error))
            raise RuntimeError(error.value or f"Erreur audio Windows {code}")
        return output.value

    def start(self, path):
        self.command(f'open "{path}" type waveaudio alias {self.alias}')
        self.opened = True
        self.command(f"set {self.alias} time format milliseconds")
        self.command(f"play {self.alias}")

    def pause(self):
        self.command(f"pause {self.alias}")

    def resume(self):
        self.command(f"resume {self.alias}")

    def replay(self):
        self.command(f"seek {self.alias} to start")
        self.command(f"play {self.alias}")

    def mode(self):
        return self.command(f"status {self.alias} mode")

    def close(self):
        if self.opened:
            try:
                self.command(f"close {self.alias}")
            finally:
                self.opened = False


AUDIO_ERRORS = (ImportError, OSError, RuntimeError, ValueError, wave.Error, EOFError)


class LocalAudioPlayer:
    """WAV asynchrone : MCI Windows, aplay Linux. Absence/erreur = silence."""

    def __init__(self, root, audio_root="audio/files", lead_in_ms=800):
        self.root = Path(root).resolve()
        self.audio_root = (self.root / audio_root).resolve()
        if not self.audio_root.is_relative_to(self.root):
            raise ValueError("Le répertoire audio doit rester dans le projet.")
        if type(lead_in_ms) is not int or not 0 <= lead_in_ms <= 5000:
            raise ValueError("Le silence initial doit être compris entre 0 et 5000 ms.")
        self.lead_in_ms = lead_in_ms
        self.process = None
        self.windows = None
        self.last_error = None
        self._state = "unavailable"
        self._path = None
        self._selection = None

    @property
    def state(self):
        if self._state == "playing":
            try:
                if self.windows and self.windows.mode() == "stopped":
                    self._state = "ready"
                elif self.process and self.process.poll() is not None:
                    self._state = "ready"
            except AUDIO_ERRORS as exc:
                self.last_error = str(exc)
                self.stop()
        return self._state

    def play(self, segment_id, audio_file=None):
        self.last_error = None
        self.stop()
        try:
            path = (self.audio_root / f"{segment_id}.wav").resolve()
            if not path.is_file() and audio_file:
                path = (self.root / audio_file.replace("{segment_id}", segment_id)).resolve()
            if not path.is_relative_to(self.root) or not path.is_file():
                return False
            self._path = wave_with_lead_in(path, self.lead_in_ms, self.root / "tmp/audio_playback")
            self._selection = (segment_id, audio_file)
            if sys.platform == "win32":
                if self.windows is None:
                    self.windows = WindowsWavePlayer()
                self.windows.start(self._path)
            else:
                player = shutil.which("aplay")
                if player is None:
                    self.stop()
                    return False
                self.process = subprocess.Popen([player, "-q", str(self._path)], stdin=subprocess.DEVNULL,
                                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._state = "playing"
            return True
        except AUDIO_ERRORS as exc:
            self.last_error = str(exc)
            self.stop()
            return False

    def pause(self):
        if self.state != "playing":
            return False
        try:
            if self.windows:
                self.windows.pause()
            elif self.process:
                self.process.send_signal(signal.SIGSTOP)
            self._state = "paused"
            return True
        except AUDIO_ERRORS as exc:
            self.last_error = str(exc)
            self.stop()
            return False

    def resume(self):
        state = self.state
        if state == "ready":
            return self.replay()
        if state == "playing":
            return True
        if state != "paused":
            return False
        try:
            if self.windows:
                self.windows.resume()
            elif self.process:
                self.process.send_signal(signal.SIGCONT)
            self._state = "playing"
            return True
        except AUDIO_ERRORS as exc:
            self.last_error = str(exc)
            self.stop()
            return False

    def replay(self):
        if self._selection is None:
            return False
        try:
            if self.windows:
                self.windows.replay()
                self._state = "playing"
                return True
            return self.play(*self._selection)
        except AUDIO_ERRORS as exc:
            self.last_error = str(exc)
            self.stop()
            return False

    def stop(self):
        try:
            if self.windows:
                self.windows.close()
            if self.process and self.process.poll() is None:
                # Un aplay suspendu doit reprendre pour traiter sa terminaison.
                if self._state == "paused":
                    self.process.send_signal(signal.SIGCONT)
                self.process.terminate()
                self.process.wait(timeout=1)
        except (subprocess.TimeoutExpired, *AUDIO_ERRORS) as exc:
            self.last_error = str(exc)
            if self.process and self.process.poll() is None:
                self.process.kill()
        finally:
            self.process = None
            self._path = self._selection = None
            self._state = "unavailable"
