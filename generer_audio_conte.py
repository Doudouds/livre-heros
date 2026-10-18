"""Lanceur autonome : tous les audio du Roi-grenouille, ou --book AUTRE_CONTE.

    python generer_audio_conte.py
    python generer_audio_conte.py --dry-run
    python generer_audio_conte.py --segment 1

Relancer la même commande reprend après une interruption ou un plantage.
"""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


if __name__ == '__main__':
    runtime = ROOT/'.venv-tts/Scripts/python.exe'
    needs_runtime = not any(flag in sys.argv[1:] for flag in ('--dry-run','--help','-h'))
    if needs_runtime and Path(sys.executable).resolve() != runtime.resolve():
        if not runtime.is_file():
            raise SystemExit('Environnement Chatterbox absent : voir docs/creation_conte_audio.md.')
        os.execv(str(runtime),[str(runtime),'-u',str(Path(__file__).resolve()),*sys.argv[1:]])
    from tools.generate_story_audio import main
    raise SystemExit(main())
