# Les Portes de l'Imaginaire

Moteur de contes fantastiques interactifs pour 9–13 ans. Application PC Python,
entièrement hors ligne, avec textes locaux, douze décisions et deux choix à chaque
décision. Aucun modèle IA ni appel réseau ne s'exécute pendant une partie.

## Jouer sur ce PC

**Double-cliquer sur `Lancer.cmd`.** Le lanceur utilise le Python fourni avec Codex
sur ce PC, une installation locale `.venv` si elle existe, sinon `py -3`.
Choisir une proposition dans chacune des trois catégories, puis « Commencer
l'aventure ». Les touches A/B ou gauche/droite correspondent aux deux boutons.
Lire la conséquence, puis cliquer sur « Poursuivre ». Le texte se fait défiler
avec la souris. Une nouvelle aventure repart avec un état entièrement neuf.

L'application ne demande aucun compte, aucun inventaire à gérer et aucune saisie
libre en mode normal. Le héros, le lieu et l'objet influencent les textes et les
possibilités. Un échec fait continuer l'aventure jusqu'à une vraie conclusion.

Sur un autre PC : Python **3.10 ou plus récent avec Tkinter** suffit. Aucun paquet
pip n'est nécessaire. Depuis le dossier du projet, dans PowerShell :

```powershell
py -3 main_pc.py
```

Sur Linux, utiliser `python3 main_pc.py` avec Tkinter disponible. Le Raspberry Pi
n'est pas encore une interface matérielle livrée : la validation PC reste prioritaire.

## Contenu livré et durée

Six familles, 114 scènes préparées et cinq conclusions par famille :

| Aventure | Sujet |
| --- | --- |
| La Lanterne des routes perdues | Un artefact disparu et des chemins à partager |
| Le Pacte de la cloche endormie | Une puissance protectrice et un accord oublié |
| Le Royaume des noms effacés | Un mystère de cartes et de témoignages |
| Le Premier Vol de Lume | Une griffonne à sauver et un départ à préparer |
| L'Atlas des terres impossibles | Une exploration et les limites d'une découverte |
| La Nuit des pluies suspendues | Une catastrophe magique et une eau à répartir |

La base contient **environ 161 minutes de prose distincte**, variantes et résultats
compris, donc davantage que les 120 minutes initialement visées. Ce nombre compte
les blocs écrits distincts une seule fois, sans multiplier les 125 substitutions.
Une partie n'utilise qu'une petite fraction des variantes.

**10 000 simulations : moyenne 20,87 minutes ; minimum 20,36 ; maximum 21,23.**
Toutes atteignent une conclusion avec douze décisions. L'audit des chemins, qui
prend une enveloppe conservative des variantes, donne 19,89 à 21,39 minutes.
Ces valeurs sont des estimations à **150 mots/minute et 10 secondes de réflexion
par choix**, réglables dans `config.json`. L'application laisse lire à son rythme :
elle n'impose pas vingt minutes d'attente. Chronométrer de vrais essais, puis les
futurs WAV, reste nécessaire pour vérifier la durée réellement vécue.

Les rapports reproductibles sont dans `reports/validation.json`,
`reports/simulation_10000.json` et `reports/configurations_125.json`.

## Mode debug et reproduction

Menu **Outils → Mode debug**, ou :

```powershell
.\Lancer.cmd --debug --seed 42 --arc lantern
```

Le bloc debug affiche l'arc, l'ID de scène, les variantes, l'acte, les décisions
passées, la durée estimée, l'inventaire, les alliés, les flags, les probabilités
et les tirages. Il se masque entièrement en revenant au mode normal.
L'arc et la graine manuels sont des contrôles de développement séparés des trois
questions du joueur. En mode normal, l'arc et la graine sont aléatoires.

**Outils → Enregistrer le journal** écrit un JSON complet, pendant ou après la
partie. **Rejouer un journal** reconstitue son état, y compris une conséquence
encore en cours. Il vérifie les scènes, textes, choix, probabilités, tirages et
conclusion ; un contenu modifié ou un journal incohérent est signalé.

```powershell
py -3 -m tools.replay_session chemin_vers_le_journal.json
```

Une même graine, une même configuration et une même suite de choix reproduisent
l'aventure avec cette version du contenu. La graine ne doit pas être utilisée
pour reproduire une partie après modification des textes ou des règles.

## Validation, tests et simulations

Toutes les commandes s'exécutent depuis ce dossier. Si `py -3` n'est pas disponible,
remplacer ce préfixe par le chemin du Python utilisé par `Lancer.cmd`.

```powershell
py -3 -m unittest discover -v
py -3 -m tools.validate_content --output reports/validation.json
py -3 -m tools.simulate_stories --count 10000 --seed 20261003 --output reports/simulation_10000.json
py -3 -m tools.simulate_stories --all-configurations --seed 20261003 --output reports/configurations_125.json
```

Le dernier audit joue **125 trios × 6 arcs × 2 parcours = 1 500 aventures**.
Les tests vérifient aussi des suites constituées uniquement de réussites,
uniquement de complications ou uniquement d'échecs. Les simulations enregistrent
les durées, arcs, conclusions, résultats et fréquences d'utilisation des scènes.
`--policy a`, `--policy b` et `--policy alternate` permettent d'autres profils.

Le validateur contrôle le contrat JSON, les références, les scènes inaccessibles,
les boucles, les destinations manquantes, les conclusions, les probabilités,
les substitutions, la compatibilité des 125 configurations et les bornes de durée.
Il ne certifie pas la qualité littéraire ou le plaisir de jeu : ces aspects
nécessitent des séances de lecture et d'essai, notamment avec le public visé.
Le test PC ouvre brièvement une instance Tkinter masquée ; il nécessite une
session graphique. Dans le sandbox Codex, Tcl peut être inaccessible même lorsque
Tkinter est installé ; les tests GUI ont été exécutés hors de ce sandbox sur ce PC.

## Audio facultatif et Chatterbox

La V1 fonctionne sans aucun fichier audio. `AudioPlayer` utilise des WAV locaux,
avec `winsound` asynchrone sur Windows et `aplay` s'il est disponible sur Linux.
Un fichier absent laisse simplement le texte affiché. Aucun TTS ne s'exécute.

```powershell
py -3 -m tools.export_tts_manifest --output reports/tts_manifest.jsonl
py -3 -m tools.export_tts_manifest --session chemin_vers_le_journal.json --output reports/tts_une_partie.jsonl
py -3 -m tools.verify_tts_coverage reports/tts_manifest.jsonl
```

Le manifeste UTF-8 JSON Lines exporte la narration complète de chaque scène,
ses deux choix regroupés, et ses conséquences narratives. Il indique le locuteur,
l'émotion, le texte résolu, la durée estimée et le fichier WAV attendu. Les
narrations restent des segments longs ; les prompts et conséquences sont des
segments plus brefs et complets. Les voix seront produites séparément avec
Chatterbox. **L'export n'effectue aucune synthèse vocale.**

Les fichiers vont dans `audio/files/` avec les noms indiqués par `output_file`.
Un hash du texte fait partie de l'identifiant : une narration avec une forêt
ne réutilise donc pas par erreur le WAV d'une cité. L'interface PC lit la narration
et la conséquence disponibles. Le manifeste prépare aussi les prompts audio ;
leur lecture automatique en chaîne sera intégrée au backend destiné à une
expérience entièrement audio. L'export global est une enveloppe des états :
il peut contenir des variantes conservatrices non rencontrées dans une partie.
Pour commencer la production vocale, l'export d'une session évite de synthétiser
toutes les combinaisons en une fois.

## Architecture et ajout de contenu

```text
main_pc.py / Lancer.cmd   Application Tkinter
main_pi.py               Fabrique du même moteur ; point d'entrée GPIO à compléter
engine/                  État, règles, probabilités, transitions, validation, simulation
ui/                      Interface PC
audio/                   Abstraction et lecteur local facultatif
content/                 Catalogues, contrat JSON, arcs et scènes locaux
content/authored/        Sources éditoriales des six familles
tools/                   Compilation, validation, simulation, journaux et manifeste TTS
tests/                   Tests automatiques
reports/                 Résultats de vérification
config.json              Durée, audio et broches futures non attribuées
```

Lire `docs/architecture.md` et `content/schema.json` pour le contrat. Le moteur
charge les JSON d'`arcs/` et de `scenes/` directement. Ajouter un nouvel arc dans
ces dossiers ne nécessite aucune modification de Python. Chaque scène a un rang
et chaque transition avance exactement d'un rang ; les branches peuvent rejoindre
une scène commune. Le rang final choisit la conclusion selon l'état, avec un
repli inconditionnel.

Pour modifier les sources éditoriales livrées puis reconstruire leurs JSON :

```powershell
py -3 -m tools.build_content
py -3 -m tools.validate_content
```

Le compilateur remplace seulement les fichiers correspondant à ses sources.
Ne pas modifier leurs JSON compilés puis relancer le compilateur : reporter les
changements dans `content/authored/` ou dans les catalogues communs.

Les conditions sont déclaratives, sans `eval`. Une réussite avec complication
atteint l'objectif avec un coût ; un échec modifie l'état et continue. Les chances
d'atteindre l'objectif restent entre 35 et 90 %. Les états, journaux et simulations
ne sont exposés qu'aux outils de développement.

## Futur Raspberry Pi

`StoryEngine` est indépendant de Tkinter, de l'audio et des GPIO. Les interfaces
`InputBackend`, `DisplayBackend` et `AudioPlayer` permettent de conserver ce moteur.
`main_pi.create_runtime(...)` fournit moteur, lecteur léger et configuration GPIO.
Les deux boutons appelleront `choose(0)` et `choose(1)` puis `advance()`.
Les numéros de broche restent à `null`, à choisir avec le matériel final.
Cette livraison prépare le portage ; elle ne prétend pas tester le Pi ni livrer
un câblage, un backend GPIO ou des voix.
