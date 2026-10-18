"""Vérifier le chapitre, exporter une lecture et une planche de contrôle."""
import hashlib
import json
import random
import re
import shutil

from engine import Content
from engine.book_engine import BookEngine, validate_book
from engine.content import ROOT, word_count


def main():
    from PIL import Image, ImageChops, ImageDraw
    report_dir = ROOT / "reports/passeuse"
    manifest = json.loads((report_dir / "image_generation.json").read_text(encoding="utf-8"))
    image_dir = ROOT / "images/passeuse"
    image_dir.mkdir(parents=True, exist_ok=True)
    for record in manifest["images"]:
        target = ROOT / record.get("file", f"images/passeuse/ch1_{record['segment']:02}.png")
        if not target.exists():
            shutil.copyfile(record["source"], target)
    content = Content()
    book = content.books["passeuse_ch1"]
    validate_book(book, ROOT)
    source_hash = hashlib.sha256((ROOT / book["source"]["file"]).read_bytes()).hexdigest()
    assert source_hash == book["source"]["sha256"], "Le PDF source a changé."
    assets, hashes = [], set()
    sheet = Image.new("RGB", (1280, 7 * 234), "white")
    draw = ImageDraw.Draw(sheet)
    for index, scene in enumerate(book["scenes"]):
        path = ROOT / scene["image"]
        with Image.open(path) as original:
            original.verify()
        with Image.open(path) as original:
            rgb = original.convert("RGB")
            channels = rgb.split()
            delta = max(ImageChops.difference(channels[0], channels[1]).getextrema()[1],
                        ImageChops.difference(channels[1], channels[2]).getextrema()[1])
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in hashes:
                raise ValueError("Illustration dupliquée")
            hashes.add(digest)
            assets.append({"scene": scene["id"], "image": scene["image"], "size": list(original.size),
                           "max_channel_difference": delta})
            rgb.thumbnail((312, 208))
            x, y = (index % 4) * 320, (index // 4) * 234
            sheet.paste(rgb, (x + (320 - rgb.width) // 2, y + 20))
            draw.text((x + 8, y + 3), f"{index+1:02} - {scene['title']}", fill="black")
    sheet.save(report_dir / "illustrations_contact.png")
    lengths, seconds, variants_seen = [], [], set()
    conditional_results = 0
    for seed in range(2000):
        engine = BookEngine(content)
        rng = random.Random(seed)
        counts = [word_count(engine.current["text"])]
        while not engine.finished:
            assert not re.search(r"\b(tu|toi|tes|ton|ta|vous|votre|vos)\b", engine.current["text"], re.I)
            variants_seen.update(engine.current["selected_variants"])
            chosen = rng.randrange(2)
            default_result = engine.current["choices"][chosen]["consequence"]
            consequence = engine.choose(chosen)
            conditional_results += consequence["text"] != default_result
            engine.advance()
            counts.append(word_count(engine.current["text"]))
        assert not re.search(r"\b(tu|toi|tes|ton|ta|vous|votre|vos)\b", engine.current["text"], re.I)
        variants_seen.update(engine.current["selected_variants"])
        assert engine.state.story_progress == 27
        lengths.extend(counts[:-1])
        seconds.append(engine.state.estimated_seconds)
    report = {"chapter": 1, "decisions": 27, "passages": 28, "simulations": len(seconds),
              "source_sha256": source_hash, "narrative_person": book["narrative_person"],
              "scene_variants_exercised": len(variants_seen),
              "conditional_consequences_exercised": conditional_results,
              "words_before_choice": {"min": min(lengths), "max": max(lengths), "mean": round(sum(lengths)/len(lengths), 1)},
              "estimated_minutes": {"min": round(min(seconds)/60, 1), "max": round(max(seconds)/60, 1)},
              "assets": assets}
    (report_dir / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    engine = BookEngine(content)
    reading = ["# La petite passeuse d'étoile — lecture du chapitre 1", "",
               "Adaptation interactive du premier chapitre du roman d'Edouard Bonguet, à la troisième personne et au passé, reprise du PDF présent à la racine.",
               "Ce parcours alterne les deux choix. La conséquence retenue ouvre le passage suivant ; certaines actions modifient aussi des passages ultérieurs.",
               "Les deux possibilités sont indiquées pour la relecture. Ce parcours montre une des variations possibles du chapitre.", ""]
    prompts = ["# Illustrations du chapitre 1", "", f"28 dessins produits avec l'outil intégré ImageGen, conservés dans `{ROOT / 'images/passeuse'}`.", ""]
    while True:
        scene = engine.current
        reading.extend([f"## {scene['rank']} · {scene['title']}", "", scene["text"], ""])
        record = manifest["images"][scene["rank"]-1]
        prompts.extend([f"## {scene['rank']:02} · {scene['title']}", "", f"Fichier : `{ROOT / scene['image']}`", "", record["prompt"], ""])
        if engine.finished:
            reading.extend(["Fin du chapitre 1. Le chapitre 2 n'est pas encore adapté.", ""])
            break
        reading.extend([scene["choice_question"], ""])
        selected_choice = engine.state.story_progress % 2
        for index, choice in enumerate(scene["choices"]):
            reading.append(f"- **Choix {index+1}** : {choice['text']}")
        reading.extend(["", f"Parcours présenté : choix {selected_choice + 1}.", ""])
        engine.choose(selected_choice)
        engine.advance()
    (ROOT / "docs/lecture_passeuse_ch1.md").write_text("\n".join(reading), encoding="utf-8")
    (ROOT / "docs/illustrations_passeuse_ch1.md").write_text("\n".join(prompts), encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k != "assets"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
