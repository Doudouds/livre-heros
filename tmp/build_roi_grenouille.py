"""Préparation éditoriale initiale depuis les deux pages du PDF vérifiées."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'reports/roi_grenouille/source.txt').read_text(encoding='utf-8')
raw = raw[raw.index('Dans des temps très anciens,'):]
raw = raw[:raw.index('*     *')]
canonical = re.sub(r'\s+', ' ', raw).strip()
repairs = {
    'to ut droit':'tout droit', 'r épondit-elle':'répondit-elle', 'plonge a':'plongea',
    'a vait':'avait', 'j e lui':'je lui', 'ava it':'avait', 'grenouil le':'grenouille',
    'volon té':'volonté', 'mont er':'monter', 'voeux':'vœux', 'coeur':'cœur',
    'dit -elle':'dit-elle', 'serait -elle':'serait-elle', 'crains -tu':'crains-tu',
    'aurait -il':'aurait-il', 'celle -ci':'celle-ci', 'Prends -moi':'Prends-moi',
    'ouvre moi':'ouvre-moi',
}
for old, new in repairs.items():
    canonical = canonical.replace(old, new)
parts = canonical.split('"')
assert len(parts) % 2 == 1, 'Guillemets source non équilibrés.'
canonical = ''.join(part if i % 2 == 0 else '« ' + part.strip() + ' »' for i, part in enumerate(parts))
canonical = re.sub(r'\s*([!?;:])', r' \1', canonical)
canonical = canonical.replace('  ', ' ')
verses = {
    "Fille du roi, la plus jeune, Ouvre-moi ! Ne sais-tu plus ce qu'hier Au bord de la fontaine fraîche Tu me promis ? Fille du roi, la plus jeune, Ouvre-moi !":
    "Fille du roi, la plus jeune,\nOuvre-moi !\nNe sais-tu plus ce qu'hier\nAu bord de la fontaine fraîche\nTu me promis ?\nFille du roi, la plus jeune,\nOuvre-moi !",
    "Eh ! non, Seigneur, ce n'est pas la voiture, Mais de mon cœur l'une des ceintures. Car j'ai eu tant de peine Quand vous étiez dans la fontaine, Transformé en grenouille vilaine !":
    "Eh ! non, Seigneur, ce n'est pas la voiture,\nMais de mon cœur l'une des ceintures.\nCar j'ai eu tant de peine\nQuand vous étiez dans la fontaine,\nTransformé en grenouille vilaine !",
}
for original, verse in verses.items():
    assert original in canonical
    canonical = canonical.replace(original,verse)
for marker in ('Il arriva que la balle', 'Quand la grenouille eut obtenu',
               'Le lendemain, comme', 'Le roi dit alors', 'Mais quand l\'animal retomba',
               'Quand ils eurent roulé'):
    canonical = canonical.replace(' ' + marker, '\n\n' + marker, 1)

specs = [
    ('La balle dans la fontaine', 'sa tête grosse et affreuse.',
     ('Montrer l’endroit où la balle a disparu',
      'La princesse désigna du regard l’endroit où la balle avait disparu ; ses larmes n’avaient pas encore séché.'),
     ('Raconter comment la balle est tombée dans la fontaine',
      'La princesse essuya ses joues et chercha ses mots pour raconter la perte de son jouet.')),
    ('Le marché de la grenouille', 'te rendrai ta balle. »',
     ('Répondre aussitôt, en ne pensant qu’à sa balle',
      'La seule idée de retrouver sa balle lui faisait oublier les exigences de la grenouille.'),
     ('Observer la grenouille un instant avant de répondre',
      'La princesse regarda la grenouille au bord de l’eau et pesa un instant sa demande.')),
    ('Une promesse aussitôt oubliée', 'Je ne peux pas courir aussi vite que toi ! »',
     ('Continuer à courir vers le château',
      'La balle enfin retrouvée, la princesse ne ralentit pas.'),
     ('Jeter un regard en arrière sans s’arrêter',
      'La princesse jeta un regard en arrière, mais ses pas l’emportaient déjà vers le château.')),
    ('La visite au château', 'Que te veut cette grenouille ? »',
     ('Répondre tout de suite à son père',
      'La princesse se tourna vers son père et répondit sans chercher d’autre excuse.'),
     ('Regarder la porte avant de répondre au roi',
      'Elle regarda la porte fermée, puis revint au visage du roi avant de lui répondre.')),
    ('La promesse rappelée', 'Va et ouvre ! »',
     ('Accepter l’ordre sans discuter davantage',
      'Elle ne répondit plus à l’ordre de son père.'),
     ('Chercher une dernière fois un appui dans son regard',
      'Elle chercha encore un appui dans le regard du roi ; il attendait qu’elle tînt parole.')),
    ('À la table du roi', 'nous allons y manger ensemble. »',
     ('Baisser les yeux vers l’assiette',
      'La princesse baissa les yeux vers la table, en évitant de regarder sa compagne.'),
     ('Rester droite sur sa chaise pour approcher l’assiette',
      'Elle resta raide sur sa chaise et posa les doigts au bord de l’assiette.')),
    ('La demande de la grenouille', 'quand tu étais dans le chagrin. »',
     ('Se résoudre à la porter sans attendre',
      'Elle ne chercha plus de moyen de retarder le départ.'),
     ('Reprendre son souffle avant de la porter',
      'Elle reprit son souffle pour retenir ses larmes, sans oser contester l’ordre du roi.')),
    ('La métamorphose', "Un prince aux beaux yeux pleins d'amitié la regardait.",
     ('Regarder le jeune homme qui se tient devant elle',
      'La princesse leva les yeux vers le jeune homme qui se tenait devant elle.'),
     ('Regarder d’abord l’endroit où la grenouille est retombée',
      'Elle regarda le sol où la grenouille était retombée, puis le jeune homme qui l’avait remplacée.')),
    ('Les huit chevaux blancs', 'La voiture devait emmener le prince dans son royaume.',
     ('S’approcher de la voiture auprès du prince',
      'La princesse s’approcha de la voiture auprès du jeune roi.'),
     ('Remercier Henri avant de s’approcher de la voiture',
      'La princesse adressa au fidèle Henri un signe de remerciement avant de s’approcher de la voiture.')),
    ('Le craquement derrière la voiture', 'comme si quelque chose se brisait.',
     ('Interroger Henri tout de suite',
      'Le prince voulut connaître l’origine de ce bruit.'),
     ('Regarder d’abord si les chevaux continuent d’avancer',
      'Les chevaux continuaient d’avancer d’un même pas. Le bruit venait de derrière lui.')),
]
book = dict(id='roi_grenouille', title='Le roi-grenouille ou Henri-le-Ferré',
    author='Jacob et Wilhelm Grimm', illustrated=False, narrative_person=3,
    decision_count=10, start='roi_grenouille_01', choice_question='Que doit faire la princesse ?',
    library_label='Le conte des Grimm', open_label='Ouvrir le Roi-grenouille',
    library_description='Le conte original, à la troisième personne, avec deux choix à chaque étape.',
    ending_notice='Fin du conte · Le roi-grenouille ou Henri-le-Ferré.', restart_label='Rejouer ce conte',
    audio_lead_in_ms=0, embedded_lead_in_ms=1000,
    source=dict(file='contesdesfreresGrimm.pdf', pages=[14,15],
                canonical_text='content/authored/books/roi_grenouille_source.txt',
                adaptation='Texte conservé, corrections de césures PDF et de typographie ; ajouts limités aux choix et raccords.'),
    customization_note='La princesse, la forêt, la fontaine et la balle d’or sont conservées pour respecter le conte.',
    scenes=[])
offset = 0
for index, (title, end, first, second) in enumerate(specs, 1):
    stop = canonical.index(end, offset) + len(end)
    text = canonical[offset:stop].strip()
    choices = [dict(id=letter, text=label, consequence=consequence,
                    next=f'roi_grenouille_{index+1:02d}', flags=[])
               for letter, (label, consequence) in zip(('a','b'), (first,second))]
    scene = dict(id=f'roi_grenouille_{index:02d}', title=title, rank=index, kind='decision',
                 text=text, choices=choices, source_pages=[14] if index < 5 else [14,15] if index == 5 else [15],
                 values={}, variants=[])
    if index == 10:
        scene['choice_question'] = 'Que doit faire le prince ?'
    book['scenes'].append(scene)
    offset = stop
book['scenes'].append(dict(id='roi_grenouille_11',title='Les trois cercles du fidèle Henri',
    rank=11,kind='ending',text=canonical[offset:].strip(),choices=[],source_pages=[15],values={},variants=[]))

first = book['scenes'][0]
# Les limites suivent les phrases du PDF ; seule la voix de la grenouille
# reçoit un ton rassurant. Aucune indication technique n'est prononcée.
body = first['text']
markers = [('visage.', 'narrateur', 'emerveillement'),
           ('favori.', 'narrateur', 'neutral'),
           ('inconsolable.', 'narrateur', 'tristesse'),
           ('une pierre s\'en laisserait attendrir ? »', 'narrateur puis grenouille', 'tendresse')]
start = 0
spans = []
for end, speaker, emotion in markers:
    stop = body.index(end,start)+len(end)
    spans.append(dict(text=body[start:stop].strip(),speaker=speaker,emotion=emotion))
    start = stop
spans.append(dict(text=body[start:].strip(),speaker='narrateur',emotion='surprise'))
first['audio_spans'] = spans
assert re.sub(r'\s+',' ', ' '.join(s['text'] for s in book['scenes'])) == re.sub(r'\s+',' ',canonical)
assert ' '.join(s['text'] for s in spans) == re.sub(r'\s+',' ',body)
directory = ROOT / 'content/authored/books'
(directory/'roi_grenouille_source.txt').write_text(canonical+'\n',encoding='utf-8')
(directory/'roi_grenouille.json').write_text(json.dumps(book,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('11 passages, 10 décisions ; texte source intégral conservé.')
