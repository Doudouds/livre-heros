# Le roi-grenouille ou Henri-le-Ferré

Ouvrir **Lancer.cmd**, puis **Ouvrir le Roi-grenouille**, ou utiliser directement
**Essayer_Roi_Grenouille.cmd**.

Le conte entier du recueil fourni, pages PDF **14 et 15**, est repris dans son
ordre : 1 298 mots de texte source, répartis en **11 passages et 10 décisions**.
La narration reste à la troisième personne. Les dialogues, la promesse, la
métamorphose après le geste contre le mur et le dénouement des trois cercles
d'Henri sont conservés. Aucun baiser ni nouvelle quête n'a été ajouté.

Chaque décision propose deux gestes ou réactions possibles. Sa conséquence
ouvre le passage suivant, puis le texte du conte reprend. Les 1 024 combinaisons
de choix rejoignent les mêmes événements et le même dénouement. Le lecteur peut,
par exemple, montrer l'endroit où la balle a disparu ou raconter sa chute,
regarder la grenouille avant de répondre, ou remercier Henri avant d'approcher
de la voiture. Ces variations portent sur les actions autour du texte.

La princesse, la forêt, la fontaine et la balle d'or sont gardées telles quelles.
Les catégories de héros, de lieux et d'objets des aventures libres ne sont pas
imposées à ce conte. Il s'ouvre directement, comme le livre de la Passeuse.

Le [parcours de lecture complet](lecture_roi_grenouille.md) permet de relire
l'adaptation et les choix sans lancer l'application.

## Source et rédaction

- PDF : `contesdesfreresGrimm.pdf`, pages 14-15, recueil Hatier, 1990.
- Manuscrit : `content/authored/books/roi_grenouille.json`.
- Texte source préparé : `content/authored/books/roi_grenouille_source.txt`.
- Contenu chargé par le logiciel : `content/books/roi_grenouille.json`.

La préparation corrige les mots artificiellement coupés lors de l'extraction du
PDF et harmonise les guillemets et la ponctuation. Les corps des onze passages,
mis bout à bout, reproduisent exactement ce texte source préparé. Les choix et
leurs conséquences sont conservés dans des champs distincts.

Après une modification éditoriale, compiler avec :

```powershell
.\.venv-tts\Scripts\python.exe -m tools.author_roi_grenouille
```

Le compilateur contrôle la couverture du texte source, les transitions et les
deux possibilités par décision. Il refuse un découpage audio différent du texte.

## Premier segment audio

Seul le premier passage est demandé et généré. Le logiciel reconnaît son WAV
par l'identifiant exact du texte affiché, question et deux choix compris. Les
passages suivants restent lisibles et affichent « Audio indisponible ».
La prise livrée dure **1 min 21,69 s**, silence initial compris. Le contrôle
des paroles et l'audit des fichiers sont validés.

```powershell
python .\generer_audio_conte.py --segment 1
```

Tout le conte est désormais balisé : dialogues, narration, vingt raccords
et dix annonces de choix. Pour produire les **21 variantes audio** depuis le
PC, double-cliquer sur **Generer_audio_Roi_Grenouille.cmd**, ou lancer :

```powershell
python .\generer_audio_conte.py
```

Relancer la même commande reprend après un arrêt. Le premier fichier déjà
validé est conservé. `--dry-run` prépare le plan sans synthèse.
La [méthode complète](creation_conte_audio.md) décrit les balises, les
contrôles, les retries et la préparation des prochains contes.

Le script utilise `chatterbox/Recording.wav`, Chatterbox Multilingual V3 en
français et la palette approuvée de la série 3, enregistrée dans
`audio/emotion_profiles.json`. Le narrateur emploie un ton neutre entre les
passages émotionnels. La beauté du décor, la perte de la balle et l'apparition
de la grenouille reçoivent les réglages d'émerveillement, de tristesse, de
tendresse et de surprise. Aucun nom d'émotion n'est prononcé.

Les prises sont découpées sur les phrases et les mots, à 300 caractères au
maximum. Les pauses valent 150 ms. Le modèle est chargé une seule fois et les
prises réussies restent en cache. Les empreintes de la voix, des poids du
modèle, des versions et des réglages empêchent de confondre deux productions.

Le contrôle **Whisper Small local est activé** : chaque bloc est retranscrit
sans lui donner le texte attendu comme prompt. Une fin absente, des paroles
trop différentes ou une annonce de choix manquante provoquent de nouvelles
prises ; les refus et transcriptions sont conservés. Un dernier contrôle porte
sur le WAV complet, avec la narration, la question et les deux choix.
Ce contrôle intégral utilise la détection de parole pour éviter les phrases
de sous-titrage que Whisper peut inventer sur les silences ; le fichier audio
et les exigences de contenu restent identiques.
La graphie homophone « chois » parfois produite par Whisper est normalisée en
« choix » uniquement devant les numéros 1 et 2 ; les annonces manquantes,
répétées ou inversées restent refusées.

Le WAV contient **une seconde de silence PCM au tout début**. Le lecteur
n'ajoute pas les 800 ms habituelles pour ce conte : le fichier et l'application
ont ainsi la même amorce. Les fichiers des autres histoires restent intacts.

Le dossier final est `audio/experiments/roi_grenouille/files`. Le plan vocal,
les réglages par passage et le contrôle final sont dans
`reports/roi_grenouille/audio_premier_segment.json` pour la première prise.
Le lot complet enregistre son plan dans `reports/roi_grenouille/audio_plan.json`
et son état par fichier dans `reports/roi_grenouille/generation_status.json`.
Les journaux et reprises sont dans le cache ; relancer la même commande
reprend les blocs déjà vérifiés.

Après génération, vérifier les fichiers présents avec :

```powershell
.\.venv-tts\Scripts\python.exe -m tools.audit_faithful_audio
```

Cet audit porte sur le **premier segment uniquement**. Il compare le texte au passage réellement chargé par l'application,
contrôle les empreintes et les transcriptions enregistrées, puis reconstitue
le WAV à l'échantillon près depuis ses prises validées. Il vérifie aussi la
seconde de silence initial et l'absence de silence ajouté par le lecteur.
Le résultat est enregistré dans
`reports/roi_grenouille/audio_audit.json`.

La reconnaissance automatique vérifie les paroles, pas l'émotion ni chaque
nuance de prononciation. L'écoute du premier passage sert à valider le rendu
avant de demander la suite du conte.
