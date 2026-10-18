# Premier essai audio de la Passeuse

Le premier segment découpé a été validé à l'écoute. Pour produire tous les
autres textes et leurs variantes, suivre le
[guide de génération du chapitre 1](generation_audio_chapitre1.md).

Le point d'entrée est `tools/generate_book_audio.py`. Il prend le texte actuel
du livre dans `content/books/passeuse_ch1.json`, via le même moteur que le jeu.
Par défaut, il produit seulement le **segment 1**, « Quelques minutes avant la
sonnerie », avec sa question et ses deux choix. Le manuscrit PDF et le script
d'essai fourni restent disponibles comme références.

## Lancer l'essai

Depuis PowerShell, dans `D:\livre_heros` :

```powershell
.\.venv-tts\Scripts\python.exe -m tools.generate_book_audio --dry-run
.\.venv-tts\Scripts\python.exe -u -m tools.generate_book_audio
```

Le deuxième lancement utilise `chatterbox/Recording.wav`. La comparaison avec
une prise longue a été retirée de ce point d'entrée après validation du test.

L'essai réel du 11 octobre 2026 a produit **81,19 s** avec les six blocs,
contre **39,96 s** pour la prise longue. Celle-ci a atteint les 1 000 tokens
autorisés par l'[implémentation officielle](https://github.com/resemble-ai/chatterbox/blob/master/src/chatterbox/mtl_tts.py).
L'assemblage a été vérifié octet par octet : les six WAV intermédiaires sont
présents dans l'ordre, avec exactement cinq pauses de 150 ms. Aucun contrôle
Whisper n'a été effectué pour ces prises ; l'écoute doit encore vérifier les
mots, les répétitions et les transitions.
Les mesures et les réglages sont conservés dans
`reports/passeuse_audio/segment_01_result.json` et le journal complet dans
`reports/passeuse_audio/generation.log`. Les 33 tests ciblés audio ont réussi.

Les deux WAV sont dans `audio/experiments/passeuse_ch1/files`. Le fichier normal
est l'assemblage des blocs ; celui qui se termine par `_single_take.wav` est
la prise longue témoin. Un même modèle et les conditionals de la même référence
sont réutilisés pour les deux. La prise témoin peut présenter précisément les
omissions ou fins prématurées que l'on cherche à mesurer. Les graines sont
reproductibles par bloc, et changent entre les tentatives ; les deux méthodes
n'ont donc pas des tirages aléatoires identiques.

## Réglages

Les constantes en haut du script sont faciles à changer :

```python
MAX_CHARS = 300
PAUSE_MS = 150
CFG_WEIGHT = 0.30
EXAGGERATION = 0.40
```

Ces deux derniers réglages reprennent le test « lent » de
`chatterbox/test_chatter_from_voice.py`. La température reste à `0.8`, valeur
par défaut de l'[API officielle](https://github.com/resemble-ai/chatterbox/blob/master/src/chatterbox/mtl_tts.py).
Le script sélectionne explicitement Multilingual V3 et le français. La voix est
préparée une seule fois, avant le premier bloc ; aucun `audio_prompt_path`
n'est passé aux appels suivants.

On peut remplacer les constantes à la ligne de commande :

```powershell
.\.venv-tts\Scripts\python.exe -m tools.generate_book_audio --chunk-chars 350 --pause-ms 200 --output-dir audio/experiments/passeuse_ch1/essai_350
```

Le découpage normalise les espaces et conserve tous les mots et signes de
ponctuation. Il privilégie les phrases complètes, y compris les guillemets
fermants. Une phrase dépassant la limite est coupée à `;` ou `:`, puis entre
deux mots si nécessaire. Les abréviations usuelles et les initiales sont
traitées par des règles simples ; ce n'est pas un analyseur linguistique complet.
Un mot plus long que la limite provoque une erreur explicite.

Avec le texte actuel, les six blocs ont 226, 239, 248, 281, 270 et 114 caractères.
Ils sont plus courts que la cible lorsque préserver une phrase complète l'exige.
Les 150 ms sont du silence **ajouté** entre deux blocs, sans silence supplémentaire
au début ou à la fin. Les silences déjà générés par Chatterbox sont conservés
pour éviter de rogner des phonèmes.

Le CPU est sélectionné comme dans l'ancien essai. `--device auto` permet
d'utiliser CUDA si une installation PyTorch adaptée et un GPU sont disponibles.

## Fichiers de suivi et reprise

- `reports/passeuse_audio/segment_01_plan.json` : texte attendu et blocs ordonnés.
- `audio/experiments/passeuse_ch1/cache/chunk_events.jsonl` : numéro du bloc,
  nombre de caractères, aperçu du texte, durée audio, temps de calcul et résultat.
- `audio/experiments/passeuse_ch1/cache/<profil>/chunks` : WAV intermédiaires et
  reçus contenant leur texte, leur graine et leur empreinte.
- `audio/experiments/passeuse_ch1/cache/<profil>/rejected` : prises rejetées et
  erreurs de génération ou de vérification.

Relancer la même commande reprend les blocs valides. Une interruption ne publie
pas de WAV final partiel. Les voix, poids, versions et paramètres font partie du
profil de cache. Changer un réglage demande un autre dossier de sortie, ou
`--overwrite` pour remplacer explicitement les WAV précédents. Les poids sont
figés à la révision du premier téléchargement, conservée dans le cache.
Pour cet essai, les poids V3 déjà présents sur le PC sont repris à la révision
`5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18`, celle du cache de l'essai précédent.

## Whisper optionnel

Le premier essai fonctionne sans Whisper : « succès » signifie que la génération
a fourni un WAV valide, et ne prouve pas que tous les mots ont été prononcés.
Il faut écouter la prise. Le mécanisme de transcription et de comparaison est
déjà disponible dans `audio/speech_verification.py` :

```powershell
.\.venv-tts\Scripts\python.exe -m pip install faster-whisper
.\.venv-tts\Scripts\python.exe -m tools.generate_book_audio --verify
```

Chaque bloc est retranscrit en français puis comparé au texte attendu. La
comparaison tolère jusqu'à 15 % d'erreurs de mots, exige les derniers mots et
contrôle les annonces de choix. Un bloc suspect est régénéré avec une nouvelle
graine, jusqu'à trois essais par défaut (`--attempts`). Le moteur peut ensuite
essayer des sous-blocs plus courts. Les transcriptions sont dans les reçus et
les rapports de rejet. Une erreur de reconnaissance, notamment sur un nom,
peut refuser une prise correcte : garder l'écoute comme contrôle final.

Activer Whisper sur des prises déjà produites les contrôle sans refaire leur
synthèse si elles passent la comparaison.

## Après validation du premier segment

```powershell
# Tous les textes du chapitre 1, toutes variantes accessibles incluses
.\.venv-tts\Scripts\python.exe -u .\generer_audio_chapitre1.py

# Segment suivant, après le choix 2 du premier segment
.\.venv-tts\Scripts\python.exe -m tools.generate_book_audio --segment 2 --choice 2

# Chapitre 1 complet, parcours reproductible choisissant toujours le choix 1
.\.venv-tts\Scripts\python.exe -m tools.generate_book_audio --chapter --choice 1
```

Le livre est interactif : le texte des segments suivants dépend des choix.
`--chapter` assemble **un parcours** du premier chapitre en un seul texte logique
puis en un seul WAV. Il ne juxtapose pas les conséquences de choix incompatibles.
`generer_audio_chapitre1.py` couvre toutes les variantes accessibles, chacune
dans son WAV. Pour un segment ultérieur isolé, `--choice` indique le choix appliqué à
chaque décision précédente.

## Recréer l'environnement

Python 3.11 est utilisé. L'installation officielle peut télécharger plusieurs
gigaoctets de dépendances et de poids au premier essai.

```powershell
python -m venv .venv-tts
.\.venv-tts\Scripts\python.exe -m pip install "git+https://github.com/resemble-ai/chatterbox.git@5de7a54aa4e5e2baadb0182dde554908b48b85c2"
```

`reports/passeuse_audio/requirements-lock.txt` conserve les versions installées
pour cet essai. Il permet de réinstaller ce même ensemble avec `pip install -r`.
Le guide général `docs/chatterbox_v3.md` reste consacré à la production des
autres contes avec vérification obligatoire.
