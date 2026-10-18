# Générer les voix de La Maison aux Sept Cages

Ouvrir PowerShell dans le projet, puis lancer :

```powershell
Set-Location D:\livre_heros
.\.venv-tts\Scripts\python.exe -u .\generer_audio_sept_cages.py
```

Le script utilise l'environnement `.venv-tts` déjà installé et la même voix que
la Passeuse, `chatterbox/Recording.wav`. Il tourne ensuite seul : garder la
fenêtre PowerShell ouverte et éviter la mise en veille pendant le calcul.

Il prépare les textes avec le moteur du conte : héros, lieux, objets, trois
trames, deux choix par décision et leurs issues (succès, complication, échec).
Les configurations initiales sont les 125 combinaisons de héros, lieu et objet.
Un texte identique n'est produit qu'une fois ; les états équivalents sont
fusionnés et les variantes impossibles ne sont pas générées.

Les paramètres par défaut sont ceux du premier essai de la Passeuse :

- Chatterbox Multilingual V3, français, CPU.
- Blocs linguistiques de **300 caractères maximum**.
- **150 ms** de pause entre les blocs.
- `cfg_weight = 0.30`, `exaggeration = 0.40`, `temperature = 0.8`.
- Une seule préparation de la voix et un seul chargement du modèle par exécution.
- Whisper désactivé ; `--verify` permet de l'activer s'il est installé.

L'introduction, chaque passage avec ses deux choix et chaque conclusion sont
des WAV séparés. La conséquence du choix ouvre le passage suivant, comme dans
le jeu. Un parcours utilise 14 WAV ; le lot complet contient davantage de
fichiers car il couvre les variantes des parcours.

## Commencer par un petit essai

Produire uniquement l'introduction pour Explorateur / Forêt / Boussole :

```powershell
.\.venv-tts\Scripts\python.exe -u .\generer_audio_sept_cages.py --hero explorer --location forest --item compass --limit 1
```

Pour écouter ce test, ouvrir `Lancer.cmd`, cliquer sur **Ouvrir le conte**,
sélectionner ces trois réponses, puis commencer l'aventure. Les WAV sont écrits
directement dans `audio/files`, le dossier déjà lu par l'application. Si un
passage manque, le jeu continue avec son texte. Le silence initial de 800 ms
réglé dans `config.json` s'applique aussi aux audios du conte.

Quand cet essai convient, lancer la commande complète en haut de cette page.
Le WAV testé sera conservé, ainsi que ses blocs en cache.

## Voir le plan sans générer de voix

```powershell
.\.venv-tts\Scripts\python.exe -u .\generer_audio_sept_cages.py --dry-run
```

Le calcul du catalogue complet peut prendre quelques minutes. La console
indique sa progression par configuration, puis le nombre de WAV, les blocs
distincts, la durée audio et le stockage estimés. La durée annoncée est la somme
des variantes, pas la durée d'une partie ni le temps de calcul de Chatterbox.

Avec les textes actuels, le plan complet contient **3 049 WAV**, couvrant les
30 scènes, et **950 blocs distincts** à synthétiser (14 343 blocs assemblés).
Les WAV finaux représentent environ **11,13 Gio**, auxquels s'ajoutent les
caches. Les 69,14 heures affichées correspondent à la durée audio estimée de
toutes les variantes réunies. Prévoir un long calcul sur CPU ; un petit lot
avec `--limit 1` permet d'abord de tester la voix.

Le catalogue a été comparé aux textes du moteur sur **1 125 parties** couvrant
les 125 configurations et les trois trames, soit 15 750 passages contrôlés.
Le rapport est `reports/cages_audio/catalog_validation.json`. Ce contrôle
vérifie les textes et noms des fichiers, sans produire d'audio ni vérifier les paroles.

Le plan est `reports/cages_audio/plan.json` : chaque fichier y est associé à
son titre, son texte exact et ses blocs. Il est recalculé à chaque lancement
selon le contenu actuel et la sélection demandée. `--plan-output chemin.json`
permet de garder plusieurs plans.

Les WAV finaux restent dans `audio/files`. Le cache et les journaux sont dans
`audio/experiments/cages/cache` (`chunk_events.jsonl` pour les blocs et
`events.jsonl` pour les fichiers). Le cache conserve les mêmes poids V3 que
la Passeuse lorsque leur révision est déjà connue, sans les télécharger à nouveau.

## Arrêter, reprendre et ajuster

**Ctrl+C** interrompt le script. Relancer exactement la même commande reprend
avec les WAV et blocs terminés. Conserver le cache et les reçus `.wav.json`.
Une fin avec `failed: 0` signifie que tous les WAV sélectionnés sont produits ;
sans Whisper, cela vérifie leur intégrité, les paroles restent à contrôler à l'écoute.

Les options peuvent se combiner :

```powershell
# Toutes les variantes pour une seule configuration.
.\.venv-tts\Scripts\python.exe -u .\generer_audio_sept_cages.py --hero explorer --location forest --item compass

# Un petit lot avec les réglages souhaités.
.\.venv-tts\Scripts\python.exe -u .\generer_audio_sept_cages.py --limit 3 --chunk-chars 300 --pause-ms 150
```

`--plot quiet`, `--plot visitor` ou `--plot departure` limite à une trame.
`--scene cages_1` limite à une scène ; cette option peut être répétée.
`--voice chemin.wav` change la référence. Les valeurs permanentes sont en haut
de `tools/generate_cages_audio.py`.

Changer la voix ou les paramètres d'un lot commencé demande un autre
`--output-dir`, ou `--overwrite` pour remplacer explicitement les WAV existants.
Le jeu lit par défaut `audio/files` : garder cette sortie pour le lot destiné
à l'application. Les prises longues de comparaison sont désactivées.
