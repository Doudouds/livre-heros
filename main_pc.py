"""Application PC : py -3 main_pc.py [--debug --seed 42]."""
import argparse
import sys

from engine import Content


def main():
    parser = argparse.ArgumentParser(description="Contes fantastiques interactifs, hors ligne")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--seed", type=int, help="Graine reproductible, active le debug")
    parser.add_argument("--arc", help="Arc imposé, active le debug")
    parser.add_argument("--pilot", action="store_true", help="Essayer La Maison aux Sept Cages, sans debug")
    parser.add_argument("--book", help="Ouvrir directement un livre ou conte fidèle, par son identifiant")
    parser.add_argument('--automatic', action='store_true', help='Écoute continue du livre, parcours du choix 1 sans annonces')
    args = parser.parse_args()
    if args.automatic and not args.book:
        parser.error('--automatic nécessite --book IDENTIFIANT.')
    try:
        import tkinter as tk
    except ImportError as exc:
        print(f"Tkinter manque dans cette installation Python : {exc}", file=sys.stderr)
        return 1
    try:
        from ui.pc_ui import PcUI
        content = Content()
        if args.book is not None and args.book not in content.books:
            raise ValueError("Livre ou conte inconnu : " + args.book)
        root = tk.Tk()
        PcUI(root, content, debug=args.debug or args.seed is not None or args.arc is not None,
             seed=args.seed, arc=args.arc or ("cages" if args.pilot else None), book=args.book,
             automatic=args.automatic)
        root.mainloop()
    except (ImportError, OSError, ValueError, tk.TclError) as exc:
        print(f"Impossible de lancer l'application : {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
