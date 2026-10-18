import json
from pathlib import Path

path = Path("reports/passeuse/image_generation.json")
manifest = json.loads(path.read_text(encoding="utf-8"))
manifest["images"][13]["prompt"] = """Use case: illustration-story
Primary request: One realistic black and white pencil drawing, horizontal. A fully clothed ADULT twenty-five-year-old woman with long dark hair tied back, wearing a loose long-sleeved work jacket and full-length work trousers with shoes, carefully crouches while moving along a narrow steel ventilation passage. Medium-wide view, her entire outfit covers torso and legs. She looks toward a faintly moonlit metal grille at the exit, listening with concern to distant elevator machinery. Suspenseful escape scene in an austere retro-industrial building. Realistic anatomy, hand-drawn graphite shading and clean paper, literary illustration. No nudity, no exposed skin apart from face and hands, no sexual content. Strictly monochrome, no text, no lettering, no watermark."""
path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
