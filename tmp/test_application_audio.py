"""Essai local du point d'entrée PC et de MCI Windows, sans génération TTS."""
import hashlib
import json
import sys
import tkinter as tk
import wave
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import main_pc
from ui.pc_ui import PcUI

apps, played, errors, positions = [], [], [], {}
original_init = PcUI.__init__
original_loop = tk.Tk.mainloop


def observe_init(app, *args, **kwargs):
    original_init(app, *args, **kwargs)
    apps.append(app)
    native_play = app.audio.play

    def observe_play(segment_id, audio_file=None):
        result = native_play(segment_id, audio_file)
        played.append(dict(segment_id=segment_id, audio_file=audio_file,
                           started=result, error=app.audio.last_error))
        return result

    app.audio.play = observe_play


def run_trial(root, *args, **kwargs):
    root.withdraw()
    app = apps[-1]
    # Les exceptions dans les callbacks Tk ne doivent pas être perdues.
    root.report_callback_exception = lambda kind, value, tb: errors.append(str(value))

    def open_book():
        button = next(w for frame in app.page.winfo_children()
                      for w in frame.winfo_children()
                      if w.winfo_class() == "TButton" and w["text"] == "Ouvrir le livre")
        button.invoke()
        assert played[-1]["started"] is True, played[-1]
        assert played[-1]["error"] is None, played[-1]
        assert not played[-1]["audio_file"].endswith("_single_take.wav")
        source = ROOT / played[-1]["audio_file"]
        positions["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        with wave.open(str(source), "rb") as original, wave.open(str(app.audio._path), "rb") as padded:
            silence_frames = original.getframerate() * app.audio.lead_in_ms // 1000
            assert padded.readframes(silence_frames) == b"\0\0" * silence_frames
            assert padded.readframes(padded.getnframes()) == original.readframes(original.getnframes())
            positions["playback_seconds"] = padded.getnframes() / padded.getframerate()

    def position():
        return int(app.audio.windows.command(f"status {app.audio.windows.alias} position"))

    def pause():
        app.audio_buttons["pause"].invoke()
        assert app.audio.state == "paused", app.audio.last_error
        positions["paused_ms"] = position()

    def resume():
        positions["after_pause_ms"] = position()
        assert abs(positions["after_pause_ms"] - positions["paused_ms"]) <= 25
        app.audio_buttons["play"].invoke()
        assert app.audio.state == "playing", app.audio.last_error
        positions["resumed_ms"] = position()
        assert positions["resumed_ms"] >= positions["paused_ms"]

    def replay():
        positions["before_replay_ms"] = position()
        assert positions["before_replay_ms"] > positions["paused_ms"]
        app.audio_buttons["replay"].invoke()
        assert app.audio.state == "playing", app.audio.last_error
        positions["replayed_ms"] = position()
        assert positions["replayed_ms"] < 100
        # Rejouer doit également fonctionner depuis la pause.
        app.audio_buttons["pause"].invoke()
        app.audio_buttons["replay"].invoke()
        assert app.audio.state == "playing", app.audio.last_error
        assert position() < 100

    def next_scene():
        buttons = [w for w in app.actions.winfo_children() if w.winfo_class() == "TButton"]
        buttons[0].invoke()
        assert app.engine.current["rank"] == 2
        assert played[-1]["started"] is False, played[-1]
        assert played[-1]["error"] is None, played[-1]
        assert app.engine.current["text"] in app.body.get("1.0", "end")
        assert all(str(b["state"]) == "disabled" for b in app.audio_buttons.values())

    def restart_and_home():
        app.restart()
        assert played[-1]["started"] is True
        app.home()
        assert app.audio.state == "unavailable"
        source = ROOT / played[-1]["audio_file"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == positions["source_sha256"]

    root.after(0, open_book)
    root.after(1400, pause)
    root.after(1800, resume)
    root.after(2200, replay)
    root.after(2500, next_scene)
    root.after(2700, restart_and_home)
    root.after(3000, app.close)
    original_loop(root, *args, **kwargs)


with patch.object(PcUI, "__init__", observe_init), patch.object(tk.Tk, "mainloop", run_trial), \
     patch.object(sys, "argv", [str(ROOT / "main_pc.py")]):
    exit_code = main_pc.main()

assert exit_code == 0, exit_code
assert not errors, errors
assert len(played) == 3, played
with wave.open(str(ROOT / played[0]["audio_file"]), "rb") as audio:
    seconds = audio.getnframes() / audio.getframerate()
result = dict(entry_point="main_pc.py (utilisé par Lancer.cmd)",
              exit_code=exit_code, real_windows_playback=True,
              first_wav_seconds=seconds, scenes=played, callback_errors=errors,
              lead_in_ms=800, controls_positions=positions)
(ROOT / "reports/passeuse_audio/application_playback_result.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
