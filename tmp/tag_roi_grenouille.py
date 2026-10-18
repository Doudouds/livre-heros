"""Application éditoriale initiale des émotions ; le manuscrit devient la source."""
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from audio.tts_batch import atomic_json
from audio.voice_markup import render_markup
from engine.content import Content

path = root/'content/authored/books/roi_grenouille.json'
book = Content.read(path)
# Chaque frontière est un extrait exact qui termine la portion précédente.
specs = {
2:[("dans la fontaine. »",'tristesse','princesse'),
   ("ton jouet ? »",'tendresse','grenouille'),
   ("sur la tête. »",'joie','princesse'),
   (None,'determination','grenouille')],
3:[("ma balle. »",'joie','princesse'),
   ("d'un être humain ?",'malice','pensée de la princesse'),
   ("sur l'herbe.",'neutral','narrateur'),
   ("partit en courant.",'joie','narrateur'),
   (None,'determination','grenouille')],
4:[("dans la fontaine.",'tristesse','narrateur'),
   ("l'escalier de marbre.",'neutral','narrateur'),
   ("ouvre-moi ! »",'determination','grenouille'),
   ("Elle avait très peur.",'peur','narrateur'),
   ("te chercher ? »",'tendresse','roi'),
   ("une vilaine grenouille. »",'peur','princesse'),
   (None,'neutral','roi')],
5:[("auprès de moi. »",'peur','princesse'),
   ("une voix dit :",'neutral','narrateur'),
   ("Ouvre-moi ! »",'determination','grenouille'),
   (None,'determination','roi')],
6:[("jusqu'à sa chaise.",'neutral','narrateur'),
   ("Prends-moi auprès de toi ! »",'determination','grenouille'),
   ("l'ordre d'obéir.",'determination','narrateur'),
   ("monter sur la table.",'neutral','narrateur'),
   (None,'determination','grenouille')],
7:[("au travers de la gorge.",'peur','narrateur'),
   ("nous allons dormir. »",'neutral','grenouille'),
   ("joli lit bien propre !",'peur','narrateur'),
   (None,'colere','roi')],
8:[("dans un coin.",'neutral','narrateur'),
   ("à ton père. »",'determination','grenouille'),
   ("affreuse grenouille ! »",'colere','princesse'),
   ("plus une grenouille.",'surprise','narrateur'),
   (None,'tendresse','narrateur')],
9:[("et son époux.",'soulagement','narrateur'),
   ("pour son royaume.",'neutral','narrateur'),
   ("harnais étaient d'or.",'emerveillement','narrateur'),
   ("C'était le fidèle Henri.",'tendresse','narrateur'),
   ("pas de douleur.",'tristesse','narrateur'),
   (None,'neutral','narrateur')],
10:[("libéré du mauvais sort.",'joie','narrateur'),(None,'surprise','narrateur')],
11:[("brise ses chaînes ? »",'surprise','prince'),
    ("grenouille vilaine ! »",'soulagement','Henri'),
    ("la voiture se brisait.",'surprise','narrateur'),
    (None,'soulagement_apaisement','narrateur')],
}
consequence_emotions = {
1:('tristesse','tristesse'), 2:('joie','neutral'), 3:('joie','neutral'),
4:('peur','peur'), 5:('determination','peur'), 6:('peur','determination'),
7:('determination','peur'), 8:('surprise','surprise'),
9:('joie','tendresse'), 10:('surprise','surprise')}
for number,scene in enumerate(book['scenes'],1):
    if number == 1:
        spans = scene['audio_spans']  # Préserver le premier audio approuvé.
    else:
        spans,offset = [],0
        for ending,emotion,speaker in specs[number]:
            end = len(scene['text']) if ending is None else scene['text'].index(ending,offset)+len(ending)
            spans.append(dict(text=scene['text'][offset:end].strip(),speaker=speaker,emotion=emotion))
            offset = end
        assert offset == len(scene['text'])
    scene['audio_markup'] = render_markup(scene['text'],spans)
    choices = scene.get('choices',[])
    for index,choice in enumerate(choices):
        emotion = consequence_emotions[number][index]
        choice['consequence_audio_markup'] = render_markup(choice['consequence'],
            [dict(text=choice['consequence'],speaker='narrateur',emotion=emotion)])
    if choices:
        question = scene.get('choice_question',book['choice_question'])
        prompt = question+' Choix 1 : '+choices[0]['text'].rstrip('.?!')+'. Ou choix 2 : '+choices[1]['text'].rstrip('.?!')+'.'
        scene['choice_audio_markup'] = render_markup(prompt,
            [dict(text=prompt,speaker='narrateur',emotion='neutral')])
book['audio_tagged_version'] = 1
atomic_json(path,book)
print('Onze passages, vingt raccords et dix annonces de choix balisés.')
