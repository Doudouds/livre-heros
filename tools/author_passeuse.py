"""Compiler le manuscrit du premier chapitre sans modifier sa rédaction."""
import hashlib
import json

from engine.content import ROOT
from engine.book_engine import validate_book


def main():
    manuscript = ROOT / "content/authored/books/passeuse_ch1.json"
    book = json.loads(manuscript.read_text(encoding="utf-8"))
    source = ROOT / book["source"]["file"]
    book["source"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    validate_book(book, ROOT)
    target = ROOT / "content/books/passeuse_ch1.json"
    target.write_text(json.dumps(book, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Chapitre compilé : {len(book['scenes'])} passages, {book['decision_count']} décisions.")


if __name__ == "__main__":
    main()
