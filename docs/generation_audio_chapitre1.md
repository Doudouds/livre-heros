# Générer les voix du chapitre 1

Ouvrir PowerShell et lancer :

```powershell
Set-Location D:\livre_heros
.\.venv-tts\Scripts\python.exe -u .\generer_audio_chapitre1.py
```

L'environnement `.venv-tts` est déjà installé. Le script tourne ensuite seul
sur le PC : la conversation n'a pas besoin de rester active. Laisser cette
fenêtre PowerShell ouverte pendant la génération et éviter la mise en veille.

Il produit **90 WAV distincts** couvrant les **28 scènes du chapitre 1**, avec
les variantes de narration, les conséquences et les choix prononcés. Le premier
segment déjà terminé est vérifié et conservé. Chaque fichier correspond au
texte exact qu'une partie peut utiliser : les conséquences sont incorporées au
début du segment suivant, comme dans le jeu. Les textes impossibles selon les
choix sont écartés, et les doublons sont produits une seule fois.

Les paramètres reprennent le premier essai validé :

- Voix : `chatterbox/Recording.wav`.
- Chatterbox Multilingual V3, français, CPU.
- `MAX_CHARS = 300`, `PAUSE_MS = 150`.
- `cfg_weight = 0.30`, `exaggeration = 0.40`, `temperature = 0.8`.
- Un seul chargement du modèle et une seule préparation de la référence vocale.
- Découpage par phrases, puis `;` / `:`, puis entre les mots si nécessaire.

## Résultats et suivi

Les WAV sont dans :

```text
D:\livre_heros\audio\experiments\passeuse_ch1\files
```

Leur nom commence par le numéro de scène, par exemple
`passeuse_1_02_narration_…wav`. Plusieurs fichiers pour une scène représentent
ses différents textes possibles. Le suffixe dépend du texte et permet au jeu
de retrouver exactement la bonne variante.

## Écouter dans l'application

Double-cliquer sur `Lancer.cmd`, puis sur **Ouvrir le livre**. L'audio correspondant
au passage affiché démarre automatiquement, avec la narration et les deux choix.
Le premier passage utilise déjà le WAV découpé validé de 81,19 secondes.

L'application ajoute **800 ms de silence au tout début de la lecture** pour
laisser le périphérique audio démarrer avant le premier mot. Ce silence vaut
pour les WAV déjà présents et ceux qui seront générés. Il se règle dans
`config.json` avec `"audio_lead_in_ms": 800` (en millisecondes, `0` le désactive).
La copie de lecture est préparée dans `tmp/audio_playback` ; les WAV originaux
et leurs reçus de génération sont conservés. Aucune nouvelle synthèse n'est nécessaire.

Trois boutons sont placés **à droite de l'illustration** :

- **▶ Lecture** reprend à la position de la pause, ou relit après la fin du son.
- **⏸ Pause** suspend la lecture en conservant sa position.
- **↺ Rejouer** relance le même passage au début, avec le silence initial.

L'état est indiqué sous les boutons. Si le WAV manque ou ne peut pas être lu,
ils sont désactivés et affichent **Audio indisponible**. Le texte et les choix
restent utilisables. Fermer puis relancer `Lancer.cmd` pour charger les modifications.

Chaque choix arrête la lecture précédente et ouvre le passage suivant. Si son
WAV n'existe pas encore, le texte reste utilisable et aucun son n'est joué.
Les nouveaux WAV seront reconnus à l'ouverture de leur passage, sans copie ni
installation supplémentaire. Recommencer le chapitre relit le premier passage ;
revenir à l'accueil ou fermer l'application arrête l'audio.

Le dossier utilisé par le livre est indiqué dans `config.json`, sous
`book_audio_roots.passeuse_ch1`. Si la génération utilise un autre `--output-dir`,
mettre ici le même dossier, à l'intérieur du projet, puis relancer l'application.

## Plan et journaux

Le plan lisible associe chaque nom de fichier à son titre, son numéro de scène,
sa variante, son texte complet et ses blocs :

```text
D:\livre_heros\reports\passeuse_audio\chapitre_1_tous_segments_plan.json
```

La console affiche chaque bloc, son nombre de caractères, le début du texte,
sa durée audio, son temps de calcul et le résultat. Les journaux persistants
sont `audio/experiments/passeuse_ch1/cache/chunk_events.jsonl` pour les blocs et
`events.jsonl` dans le même dossier pour les fichiers terminés ou en échec.
Les WAV intermédiaires sont conservés dans le cache pour la reprise.

Sur le CPU utilisé pour l'essai, prévoir plusieurs heures pour le lot complet.
Le plan contient 620 blocs assemblés, dont seulement 315 textes de blocs
distincts : le cache évite de générer les blocs identiques plusieurs fois.
L'estimation de 2,59 heures affichée au lancement représente la somme des
durées audio des variantes, **pas le temps de calcul**, ni la durée d'une partie.

## Arrêter et reprendre

Appuyer sur **Ctrl+C** pour arrêter. Relancer exactement la même commande pour
reprendre : les WAV et blocs terminés restent disponibles ; le bloc interrompu
est refait. Il faut conserver le cache et les fichiers `.wav.json`.

Une fin de traitement avec `failed: 0` signifie que tous les WAV du lot ont été
produits. En cas d'échec, le journal indique le texte concerné ; relancer la
commande permet une nouvelle tentative avec les mêmes réglages.

## Prévisualiser ou modifier les réglages

Préparer le plan sans lancer Chatterbox :

```powershell
.\.venv-tts\Scripts\python.exe .\generer_audio_chapitre1.py --dry-run
```

Changer ponctuellement la taille des blocs et les pauses :

```powershell
.\.venv-tts\Scripts\python.exe -u .\generer_audio_chapitre1.py --chunk-chars 300 --pause-ms 150
```

Les valeurs permanentes sont en haut de `tools/generate_book_audio.py`.
Changer la voix ou les paramètres après le début du lot demande un autre
`--output-dir`, ou `--overwrite` pour remplacer les WAV précédents. Garder les
mêmes réglages pendant ce premier lot permet de conserver le segment validé.

Whisper est facultatif et désactivé par défaut. Son installation et l'option
`--verify` sont expliquées dans `docs/passeuse_audio.md`. La génération courante
ne crée pas de nouvelle prise longue témoin. Celle du premier essai reste un
fichier historique dans le dossier de résultats.
