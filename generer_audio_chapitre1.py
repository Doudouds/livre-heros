r"""Générer tous les textes du chapitre 1 de La petite passeuse d'étoile.

Depuis PowerShell :
    .\.venv-tts\Scripts\python.exe -u .\generer_audio_chapitre1.py

Ajouter --dry-run pour préparer le plan sans produire d'audio.
Les WAV déjà prêts sont conservés ; relancer reprend après une interruption.
"""
import sys

from tools.generate_book_audio import main


if __name__ == '__main__':
    raise SystemExit(main(['--all-segments', *sys.argv[1:]]))
