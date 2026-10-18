import json
import shutil
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from audio.audio_player import LocalAudioPlayer, SilentAudioPlayer, wave_with_lead_in
from engine import Content, StoryEngine
from engine.book_engine import BookEngine
from engine.simulator import complete
from tools.export_tts_manifest import entry, export


def write_test_wav(path, *, width=2):
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = (b"\x01\x02" if width == 2 else b"\x81") * 2400
    with wave.open(str(path), "wb") as audio:
        audio.setparams((1, width, 24000, 0, "NONE", "not compressed"))
        audio.writeframes(frames)
    return frames


class FakeWindowsWave:
    def __init__(self):
        self.calls, self.opened, self.current_mode = [], False, "stopped"

    def start(self, path):
        self.calls.append(("start", path))
        self.opened, self.current_mode = True, "playing"

    def pause(self):
        self.calls.append(("pause",))
        self.current_mode = "paused"

    def resume(self):
        self.calls.append(("resume",))
        self.current_mode = "playing"

    def replay(self):
        self.calls.append(("replay",))
        self.current_mode = "playing"

    def mode(self):
        return self.current_mode

    def close(self):
        if self.opened:
            self.calls.append(("close",))
        self.opened, self.current_mode = False, "stopped"


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content()

    def test_no_audio_files_is_silent_and_non_blocking(self):
        with tempfile.TemporaryDirectory() as folder:
            player = LocalAudioPlayer(folder)
            self.assertFalse(player.play("missing"))
            player.stop()
        self.assertFalse(SilentAudioPlayer().play("missing"))

    def test_audio_does_not_escape_project(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "project"
            root.mkdir()
            (Path(folder) / "outside.wav").write_bytes(b"outside")
            player = LocalAudioPlayer(root)
            self.assertFalse(player.play("missing", "../outside.wav"))
            self.assertFalse(player.play("../../../outside"))

    def test_wav_backend_supports_pause_resume_replay_and_natural_end(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "audio/files").mkdir(parents=True)
            write_test_wav(root / "audio/files/segment.wav")
            import sys
            if sys.platform != "win32":
                self.skipTest("Contrôle MCI uniquement sur Windows")
            backend = FakeWindowsWave()
            with patch("audio.audio_player.WindowsWavePlayer", return_value=backend):
                player = LocalAudioPlayer(root)
                self.assertTrue(player.play("segment"))
                self.assertEqual(player.state, "playing")
                self.assertTrue(player.pause())
                self.assertEqual(player.state, "paused")
                self.assertTrue(player.resume())
                self.assertTrue(player.replay())
                backend.current_mode = "stopped"
                self.assertEqual(player.state, "ready")
                self.assertTrue(player.resume())
                self.assertEqual(player.state, "playing")
                player.stop()
                self.assertEqual(player.state, "unavailable")
                self.assertFalse(player.replay())
                self.assertEqual([c[0] for c in backend.calls],
                                 ["start", "pause", "resume", "replay", "replay", "close"])

    @unittest.skipUnless(sys.platform == "win32", "Contrôle winsound uniquement sur Windows")
    def test_playback_and_stop_errors_leave_the_player_usable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "audio/files").mkdir(parents=True)
            write_test_wav(root / "audio/files/segment.wav")
            player = LocalAudioPlayer(root)
            backend = FakeWindowsWave()
            with patch("audio.audio_player.WindowsWavePlayer", return_value=backend), \
                 patch.object(backend, "start", side_effect=RuntimeError("Périphérique indisponible")):
                self.assertFalse(player.play("segment"))
                self.assertIn("indisponible", player.last_error)
                player.stop()
                self.assertFalse(player.play("missing"))
            with patch("audio.audio_player.WindowsWavePlayer", return_value=backend):
                self.assertTrue(player.play("segment"))
                with patch.object(backend, "pause", side_effect=RuntimeError("Pause impossible")), \
                     patch.object(backend, "close", side_effect=RuntimeError("Arrêt impossible")):
                    self.assertFalse(player.pause())
                    player.stop()
                self.assertEqual(player.state, "unavailable")

    @unittest.skipUnless(sys.platform == "win32", "Contrôle winsound uniquement sur Windows")
    def test_missing_wav_is_found_after_generation_without_recreating_the_player(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "book/segment.wav"
            player = LocalAudioPlayer(root)
            backend = FakeWindowsWave()
            with patch("audio.audio_player.WindowsWavePlayer", return_value=backend):
                self.assertFalse(player.play("segment", "book/segment.wav"))
                self.assertFalse(backend.calls)
                write_test_wav(target)
                self.assertTrue(player.play("segment", "book/segment.wav"))
                self.assertEqual(player.state, "playing")
                self.assertTrue(player.pause())
                self.assertFalse(player.play("missing"))
                self.assertEqual(player.state, "unavailable")
                self.assertFalse(player.resume())
                self.assertFalse(player.replay())

    def test_leading_silence_preserves_every_sample_and_is_cached(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "audio.wav"
            frames = write_test_wav(source)
            original = source.read_bytes()
            padded = wave_with_lead_in(source, 800, root / "cache")
            with wave.open(str(padded), "rb") as audio:
                self.assertEqual(audio.getnframes(), 21600)
                self.assertEqual(audio.readframes(19200), b"\0\0" * 19200)
                self.assertEqual(audio.readframes(2400), frames)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(wave_with_lead_in(source, 800, root / "cache"), padded)
            self.assertEqual(wave_with_lead_in(source, 0, root / "cache"), source)
            self.assertNotEqual(wave_with_lead_in(source, 1000, root / "cache"), padded)
            write_test_wav(source, width=1)
            padded8 = wave_with_lead_in(source, 800, root / "cache")
            self.assertNotEqual(padded8, padded)
            with wave.open(str(padded8), "rb") as audio:
                self.assertEqual(audio.readframes(19200), b"\x80" * 19200)

    def test_corrupt_audio_is_silent_and_has_no_controls(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "corrupt.wav").write_bytes(b"invalid")
            player = LocalAudioPlayer(root)
            self.assertFalse(player.play("corrupt", "corrupt.wav"))
            self.assertEqual(player.state, "unavailable")
            self.assertFalse(player.pause())
            self.assertFalse(player.resume())
            self.assertFalse(player.replay())

    @unittest.skipUnless(sys.platform == "win32", "Contrôle winsound uniquement sur Windows")
    def test_book_ui_plays_existing_first_wav_and_continues_without_later_audio(self):
        import tkinter as tk
        from ui.pc_ui import PcUI

        engine = BookEngine(self.content)
        first_id = engine.current["segment_id"]
        audio_root = self.content.config["book_audio_roots"][engine.book["id"]]
        first_wav = self.content.root / audio_root / (first_id + ".wav")
        if not first_wav.is_file():
            self.skipTest("Le premier WAV réel n'a pas encore été généré sur ce PC")
        # Copier le vrai WAV dans un dossier isolé : les scènes suivantes restent
        # volontairement absentes, même après la génération complète du chapitre.
        with tempfile.TemporaryDirectory(dir=self.content.root / "tmp") as folder:
            relative = Path(folder).relative_to(self.content.root).as_posix()
            target = Path(folder) / first_wav.name
            shutil.copyfile(first_wav, target)
            config = {**self.content.config, "audio_root": relative + "/legacy",
                      "book_audio_roots": {"passeuse_ch1": relative}}
            root, app = tk.Tk(), None
            root.withdraw()
            try:
                backend = FakeWindowsWave()
                with patch.dict(self.content.config, config), \
                     patch("audio.audio_player.WindowsWavePlayer", return_value=backend):
                    app = PcUI(root, self.content)
                    open_book = next(w for frame in app.page.winfo_children()
                                     for w in frame.winfo_children()
                                     if w.winfo_class() == "TButton" and w["text"] == "Ouvrir le livre")
                    open_book.invoke()
                    self.assertEqual(app.engine.current["segment_id"], first_id)
                    self.assertEqual(app.audio.state, "playing")
                    self.assertEqual(backend.calls[-1][0], "start")
                    app.audio_buttons["pause"].invoke()
                    self.assertEqual(app.audio.state, "paused")
                    self.assertEqual(str(app.audio_buttons["play"]["state"]), "normal")
                    app.audio_buttons["play"].invoke()
                    self.assertEqual(app.audio.state, "playing")
                    app.audio_buttons["replay"].invoke()
                    self.assertEqual(backend.calls[-1], ("replay",))
                    app.choose(0)
                    self.assertEqual(app.engine.current["rank"], 2)
                    self.assertIn(app.engine.current["text"], app.body.get("1.0", "end"))
                    self.assertEqual(backend.calls[-1], ("close",))
                    self.assertTrue(all(str(b["state"]) == "disabled" for b in app.audio_buttons.values()))
                    # Chaque texte d'une même scène garde son propre nom de WAV.
                    first_variant = app.engine.current["segment_id"]
                    app.restart()
                    self.assertEqual(backend.calls[-1][0], "start")
                    app.choose(1)
                    self.assertNotEqual(app.engine.current["segment_id"], first_variant)
                    self.assertEqual(backend.calls[-1], ("close",))
                    for _ in range(26):
                        app.choose(0)
                    self.assertTrue(app.engine.finished)
                    app.home()
                    self.assertIsNone(app.engine)
                    self.assertEqual(app.audio.state, "unavailable")
            finally:
                if app:
                    app.audio.stop()
                root.destroy()

    def test_session_tts_has_resolved_text_and_matching_audio_paths(self):
        existing_audio = set((self.content.root / 'audio/files').glob('*.wav'))
        with tempfile.TemporaryDirectory() as folder:
            path, manifest = Path(folder)/"session.json", Path(folder)/"tts.jsonl"
            engine = StoryEngine(self.content, "rogue", "city", "book", 22, "atlas")
            complete(engine, lambda e: e.state.story_progress % 2)
            engine.export_session(path)
            count = export(self.content, manifest, path)
            records = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(count, 26)  # 14 narrations avec choix intégrés, 12 conséquences
            decisions = [r for r in records if "Que fais-tu ?" in r["text"]]
            self.assertEqual(len(decisions), 12)
            self.assertTrue(all("Choix 1 :" in r["text"] and "Ou choix 2 :" in r["text"] for r in decisions))
            self.assertTrue(all("{" not in r["text"] for r in records))
            ids = {r["segment_id"] for r in records}
            for scene in engine.journal["scenes"]:
                self.assertIn(scene["segment_id"], ids)
            for result in engine.journal["choices"]:
                self.assertIn(result["segment_id"], ids)
            self.assertTrue(all(r["output_file"].endswith(r["segment_id"] + ".wav") for r in records))
            self.assertEqual(set((self.content.root / 'audio/files').glob('*.wav')), existing_audio)

    def test_pc_ui_full_story_and_debug_visibility(self):
        import tkinter as tk
        from ui.pc_ui import PcUI
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.fail(f"L'interface Tk ne peut pas être testée : {exc}")
        root.withdraw()
        try:
            app = PcUI(root, self.content, debug=True, seed=38, arc="names")
            self.assertEqual(len(app.content.heroes), 5)
            self.assertEqual(str(app.start_button["state"]), "disabled")
            app.hero.set("rogue")
            app.location.set("city")
            app.item.set("book")
            app.check_ready()
            self.assertEqual(str(app.start_button["state"]), "normal")
            app.start()
            self.assertEqual(app.engine.current["kind"], "intro")
            self.assertTrue(app.debug_panel.pack_info())
            app.debug.set(False)
            app.toggle_debug()
            self.assertFalse(app.debug_panel.winfo_manager())
            app.advance()
            for _ in range(12):
                self.assertEqual(len([w for w in app.actions.winfo_children() if w.winfo_class() == "TButton"]), 2)
                player_text = app.body.get("1.0", "end")
                self.assertNotIn('"seed"', player_text)
                self.assertNotIn('"probabilities"', player_text)
                app.choose(0)
                self.assertEqual(len(app.actions.winfo_children()), 1)
                app.advance()
                root.update_idletasks()
            self.assertTrue(app.engine.finished)
            app.setup()
            self.assertIsNone(app.engine)
            self.assertFalse(app.hero.get() or app.location.get() or app.item.get())
        finally:
            app.audio.stop() if "app" in locals() else None
            root.destroy()


if __name__ == "__main__":
    unittest.main()
