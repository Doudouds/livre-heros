"""Contrôle des dimensions de nos propres widgets Tk, sans pilotage externe."""
import json
import tkinter as tk
from pathlib import Path

from engine import Content
from ui.pc_ui import PcUI

root = tk.Tk()
app = PcUI(root, Content())
root.geometry("800x620")
checks = []


def check(label):
    root.update()
    root.update_idletasks()
    controls = []
    def walk(widget):
        for child in widget.winfo_children():
            if child.winfo_class() == "TButton" and child.winfo_ismapped():
                bottom = child.winfo_rooty() - app.page.winfo_rooty() + child.winfo_height()
                controls.append({"text": child["text"], "bottom": bottom,
                                 "inside": bottom <= app.page.winfo_height()})
            walk(child)
    walk(app.page)
    entry = {"page": label, "height": app.page.winfo_height(), "buttons": controls}
    if app.reading_scene and app.reading_scene.get("image"):
        entry["image_width"] = app.illustration.width()
        entry["reading_width"] = app.body.winfo_width()
        entry["first_element"] = app.body.dump("1.0", "1.1", window=True)
        assert entry["image_width"] >= 360, entry
        assert entry["image_width"] <= 600, entry
        assert entry["image_width"] <= entry["reading_width"] - 48, entry
        assert entry["first_element"] == [("window", str(app.illustration_row), "1.0")], entry
        app.body.yview_moveto(1)
        root.update()
        entry["scroll_fraction"] = app.body.yview()[0]
        assert entry["scroll_fraction"] > 0, entry
        app.body.yview_moveto(0)
    checks.append(entry)
    assert len(controls) == (5 if app.reading_scene and app.reading_scene.get("image") else 2), checks[-1]
    assert all(button["inside"] for button in controls), checks[-1]


try:
    check("accueil")
    app.start_book()
    check("ouverture directe du premier passage")
    root.geometry("1100x800")
    check("premier passage, grande fenêtre")
    root.geometry("800x620")
    while not app.engine.finished:
        app.choose(0)
    check("clôture")
finally:
    app.audio.stop()
    root.destroy()
Path("reports/passeuse/layout.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(json.dumps(checks, ensure_ascii=False, indent=2))
