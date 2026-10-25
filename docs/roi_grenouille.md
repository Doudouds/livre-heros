# Le roi-grenouille ou Henri-le-Ferré

Ouvrir **Lancer.cmd**, puis **Ouvrir le Roi-grenouille**, ou utiliser directement
**Essayer_Roi_Grenouille.cmd**.

Avant d'ouvrir le conte à l'accueil, la case **Écoute automatique · sans choix**
permet de suivre le premier choix jusqu'au bout, sans annoncer les options.
Préparer les 11 WAV de ce mode avec **Generer_audio_Roi_Grenouille_Automatique.cmd**
ou `python generer_audio_conte.py --automatic`. Les fichiers et rapports de
l'écoute automatique sont distincts des versions interactives ; les prises
narratives communes sont réutilisées. Les audio doivent être prêts avant le
lancement de l'écoute complète.
`Ecouter_Roi_Grenouille_Automatique.cmd` ouvre directement ce mode après sa
préparation.

Les deux modes sont à préparer pour livrer le conte complet : **21 WAV pour le
jeu à deux choix et 11 WAV pour l'écoute automatique**. Le premier segment de
chacun annonce « Le roi-grenouille ou Henri-le-Ferré, des frères Jacob et Wilhelm Grimm. », avec
la prononciation « Grimme », après la seconde de silence initial. Les corps du
récit restent inchangés. L'annonce est balisée dans `audio_intro` du manuscrit.

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

Le premier passage est disponible dans les deux modes, avec l'annonce du titre
et de l'auteur. Le logiciel reconnaît son WAV par l'identifiant exact du texte
prononcé. Le jeu ajoute sa question et ses deux choix ; le mode automatique
lit seulement l'annonce et le récit. Les versions antérieures sans annonce
restent conservées, et les prises de narration approuvées sont réutilisées.

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
maximum. Les reprises difficiles utilisent des phrases ou propositions
complètes, sans couper après une préposition. Les pauses valent 150 ms. Les
prises réussies restent en cache. Les empreintes de la voix, des poids du
modèle, des versions et des réglages empêchent de confondre deux productions.

Le contrôle **Whisper Small local est activé** : chaque bloc est retranscrit
sans lui donner le texte attendu comme prompt. Une fin absente, des paroles
trop différentes ou une annonce de choix manquante provoquent de nouvelles
prises ; les refus et transcriptions sont conservés. **Whisper Medium**, installé
localement, arbitre les refus de Small et effectue obligatoirement le dernier
contrôle sur le WAV complet, avec la narration et les annonces du mode choisi.
Le seuil et les exigences de fin sont inchangés. Chatterbox et Medium sont
chargés à tour de rôle pour limiter la mémoire utilisée ; les paramètres de
synthèse restent les mêmes.
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
python -m tools.audit_automatic_audio --interactive --segment 1
```

Cette commande porte sur le **premier segment interactif uniquement**. Elle
compare le texte au passage réellement chargé par l'application, contrôle les
empreintes, la consigne de prononciation et les transcriptions enregistrées,
puis reconstitue le WAV à l'échantillon près depuis ses prises validées. Elle
vérifie aussi la seconde de silence initial et l'absence de silence ajouté
par le lecteur. Le résultat est enregistré dans
`reports/roi_grenouille/quality_audit_medium.json`.

## Parcours automatique complet

Les **11 WAV automatiques sont désormais prêts**, contre huit avant la
réparation. Les huit fichiers d'origine ont été revérifiés avec Medium sans
modifier leurs octets. Les portions correctes des trois passages manquants ont
été récupérées dans le cache ; seules les portions encore refusées ou absentes
ont nécessité une nouvelle prise.

Double-cliquer sur `Ecouter_Roi_Grenouille_Automatique.cmd` pour écouter le
parcours du choix 1 sans annonces. La génération reprend avec
`python generer_audio_conte.py --automatic`. Son état est conservé dans
`reports/roi_grenouille/automatic/generation_status.json`.

```powershell
python -m tools.audit_automatic_audio
```

Cet audit contrôle les onze textes réellement joués, les émotions, les
empreintes, l'assemblage exact, la seconde de silence et les preuves finales
Medium. Son résultat est dans
`reports/roi_grenouille/automatic/quality_audit_medium.json`.

La reconnaissance automatique vérifie les paroles, pas l'émotion ni chaque
nuance de prononciation. L'écoute du premier passage sert à valider le rendu
avant de demander la suite du conte.
