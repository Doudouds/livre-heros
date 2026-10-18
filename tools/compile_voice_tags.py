"""Compiler un conte entièrement balisé et vérifier sa fidélité au texte source."""
import argparse
import copy
import re
from pathlib import Path

from audio.tts_batch import atomic_json, file_hash
from audio.voice_markup import compile_book
from engine.book_engine import validate_book
from engine.content import Content, ROOT


def compile_tale(book_id, root=ROOT):
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',book_id):
        raise ValueError('Identifiant de conte invalide.')
    root = Path(root)
    manuscript = root/'content/authored/books'/(book_id+'.json')
    book = copy.deepcopy(Content.read(manuscript))
    compile_book(book,Content.read(root/'audio/emotion_profiles.json')['profiles'])
    source = book.get('source',{})
    if source.get('canonical_text'):
        canonical = (root/source['canonical_text']).read_text(encoding='utf-8')
        if ' '.join(' '.join(s['text'] for s in book['scenes']).split()) != ' '.join(canonical.split()):
            raise ValueError('Le corps du conte ne couvre plus exactement le texte source préparé.')
        source['canonical_sha256'] = file_hash(root/source['canonical_text'])
    if source.get('file'):
        source['sha256'] = file_hash(root/source['file'])
    validate_book(book,root)
    if book.get('embedded_lead_in_ms') != 1000 or book.get('audio_lead_in_ms') != 0:
        raise ValueError('Il faut 1 000 ms dans le WAV et 0 ms supplémentaires dans le lecteur.')
    atomic_json(root/'content/books'/(book_id+'.json'),book)
    return book


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--book',default='roi_grenouille')
    args = parser.parse_args(argv)
    book = compile_tale(args.book)
    print(f"Conte compilé et balisé : {book['title']} | {len(book['scenes'])} passages.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
