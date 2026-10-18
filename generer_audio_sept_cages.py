r"""Générer les textes de La Maison aux Sept Cages avec ta voix.

Depuis PowerShell :
    .\.venv-tts\Scripts\python.exe -u .\generer_audio_sept_cages.py

Ajouter --dry-run pour voir le plan, ou --limit 1 pour un premier WAV.
Relancer la même commande reprend après une interruption.
"""
from tools.generate_cages_audio import main


if __name__ == '__main__':
    raise SystemExit(main())
