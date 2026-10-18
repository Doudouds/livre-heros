"""Compiler le conte fidèle depuis son manuscrit, sans réécriture automatique."""
from tools.compile_voice_tags import compile_tale


def main():
    book = compile_tale('roi_grenouille')
    print(f"Conte compilé : {len(book['scenes'])} passages, {book['decision_count']} décisions.")


if __name__ == '__main__':
    main()
