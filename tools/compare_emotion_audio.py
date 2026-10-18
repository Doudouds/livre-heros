"""Page locale de comparaison entre deux séries d'essais vocaux."""
import argparse
import html
import json
import os
import re
from pathlib import Path

from engine.content import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--baseline', type=Path, required=True)
    args = parser.parse_args()
    directory = args.directory.resolve()
    current = json.loads((directory / 'plan.json').read_text(encoding='utf-8'))
    baseline = json.loads((args.baseline / 'plan.json').read_text(encoding='utf-8'))
    if current['voice_sha256'] != baseline['voice_sha256']:
        raise ValueError('Les deux séries utilisent des références différentes.')
    originals = {i['id']: i for i in baseline['excerpts']}
    escape = html.escape
    cards = []
    def series_label(plan):
        match = re.fullmatch(r'essai_(\d+)', plan['take'])
        return 'Série ' + str(int(match[1])) if match else plan['take']
    baseline_label, current_label = series_label(baseline), series_label(current)
    title = 'Comparer les émotions — ' + baseline_label + ' et ' + current_label

    def player(item, label):
        path = Path(item['output_file'])
        if item['status'] != 'ready' or not path.is_file():
            raise ValueError('Un des fichiers comparés manque.')
        relative = os.path.relpath(path, directory).replace(os.sep, '/')
        parameters = item['parameters']
        return ('<section><h3>' + escape(label) + '</h3><audio controls preload="none" src="'
                + escape(relative, quote=True) + '"></audio><p class="settings">Expressivité : '
                + str(parameters['exaggeration']) + ' · Guidage : ' + str(parameters['cfg_weight'])
                + ' · ' + str(item['seconds']) + ' s</p></section>')

    for item in current['excerpts']:
        original = originals[item.get('baseline_id', item['id'])]
        if item['text'] != original['text']:
            raise ValueError('Les textes comparés sont différents.')
        accepted = item.get('decision') == 'accepted'
        card = '<article><h2>' + escape(item['emotion']) + '</h2>'
        card += '<p class="feedback">Ton retour : ' + escape(item.get('feedback', '')) + '</p>'
        card += '<blockquote>' + escape(item['text']) + '</blockquote>'
        if item.get('composition'):
            card += '<p class="accepted">Début retravaillé ; seconde partie conservée.</p>'
        if item.get('review_note'):
            card += '<p class="feedback">' + escape(item['review_note']) + '</p>'
        if accepted:
            card += '<p class="accepted">Prise validée et conservée.</p>' + player(item, 'Prise conservée')
        else:
            card += '<div class="pair">' + player(original, baseline_label) + player(item, current_label) + '</div>'
        cards.append(card + '</article>')

    page = '''<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>body{font:17px/1.5 system-ui;max-width:1050px;margin:32px auto;padding:0 20px;background:#f7f5f0;color:#242a32}h1{font-size:30px}h2{font-size:23px}h3{font-size:17px}article{background:white;padding:22px 28px;margin:22px 0;border-radius:14px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:24px}audio{width:100%}.settings,.feedback{font-size:14px;color:#586270}.accepted{color:#25603d;font-weight:600}blockquote{margin:16px 0}@media(max-width:700px){.pair{grid-template-columns:1fr}}</style>
<h1>__TITLE__</h1>
<p>Même texte et même référence vocale. Les prises déjà validées sont conservées.</p>
<p>Écoute les prises successivement, au même volume. Pour chaque numéro, indique si l'intention est plus perceptible et si la voix reste naturelle.</p>
<script>document.addEventListener('play',event=>{if(event.target.tagName==='AUDIO'){document.querySelectorAll('audio').forEach(audio=>{if(audio!==event.target)audio.pause()})}},true)</script>'''
    page = page.replace('__TITLE__', escape(title))
    previous = args.baseline.resolve() / 'comparer.html'
    if previous.is_file():
        relative = os.path.relpath(previous, directory).replace(os.sep, '/')
        page += '<p><a href="' + escape(relative, quote=True) + '">Comparaison précédente</a></p>'
    (directory / 'comparer.html').write_text(page + '\n'.join(cards) + '</html>\n', encoding='utf-8')
    print(directory / 'comparer.html')


if __name__ == '__main__':
    main()
