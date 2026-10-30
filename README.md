# Les Portes de l'Imaginaire

## Application Android

Une **application Android native en Kotlin** contrôle le lecteur : bibliothèque,
jeu à deux choix, écoute automatique, Lecture/Pause/Reprise, Rejouer, Recommencer,
volume et progression. Le son reste sur le PC ; le même protocole pourra servir
au Raspberry Pi.

Lancer **Telecommande_Telephone.cmd**, puis ouvrir sur le téléphone le lien
**Application Android** affiché dans la console pour télécharger l’APK. Après
installation, saisir dans l’application l’adresse du lecteur et son code à huit
chiffres. Les deux appareils doivent partager le même réseau local.

L’APK est produite dans `dist/android/LesPortesImaginaire.apk`, hors de Git.
**Compiler_Application_Android.cmd** la reconstruit avec Android Studio/son SDK,
les tests et les vérifications Android. Le projet se trouve dans `android/`.
[Installation, compilation et limites de cette première version](docs/application_android.md).

## Contrôler le PC depuis un téléphone

Double-cliquer sur **Telecommande_Telephone.cmd**, puis ouvrir sur le téléphone
l’adresse « Téléphone » affichée dans la fenêtre. Les deux appareils doivent
être sur le même réseau local. Si la page demande un code, saisir les huit
chiffres affichés sur le PC. Autoriser Python sur le réseau **privé** si Windows
le demande ; garder la fenêtre du lanceur ouverte.

La télécommande propose la bibliothèque, les deux modes des contes préparés,
les choix interactifs, Lecture/Pause/Reprise, Rejouer le passage, Recommencer,
Arrêter, le volume et la progression audio sous Windows. **Le son sort du PC.**
L’écoute automatique continue même lorsque le téléphone est verrouillé ou
déconnecté. Les fichiers absents suspendent ce mode sans sauter de passage.

Ce lanceur fonctionne séparément de l’application Tkinter. Les commandes ne
pilotent pas une fenêtre déjà ouverte avec `Lancer.cmd`. Il ne génère aucun son
nouveau et ne demande aucun paquet pip. [Guide de connexion et de dépannage](docs/telecommande_telephone.md).

## Générer les audio d'un conte

Chaque conte doit être produit dans **les deux modes** : jeu avec toutes les
variantes des deux choix, et écoute automatique sur le choix 1 sans annonces.
Lancer les deux commandes : `python generer_audio_conte.py --book IDENTIFIANT`
puis `python generer_audio_conte.py --book IDENTIFIANT --automatic`.
Le premier audio de chaque mode annonce le titre et l'auteur après la seconde
de silence initial. Pour le Roi-grenouille, « Grimm » se prononce « Grimme ».

Double-cliquer sur **Generer_audio_Roi_Grenouille.cmd**, ou exécuter
`python generer_audio_conte.py`. Le lanceur génère les 21 variantes du conte,
avec émotions balisées, contrôle des paroles, essais automatiques et reprise
après interruption. Relancer la même commande conserve les fichiers validés.
`python generer_audio_conte.py --dry-run` prépare seulement le plan.
Après des refus du vérificateur, cette commande réexamine le cache sans lancer
de nouvelle synthèse :

```powershell
python generer_audio_conte.py --automatic --recheck-only
```

Pour écouter sans prendre de décisions, cocher **Écoute automatique · sans
choix** avant d'ouvrir le Roi-grenouille. Ce mode suit le premier choix et
enchaîne les passages sans lire les questions ou les options. Préparer ses
**11 fichiers** avec **Generer_audio_Roi_Grenouille_Automatique.cmd**, ou
`python generer_audio_conte.py --automatic`. Pause et Rejouer restent disponibles.
Les fichiers interactifs existants sont conservés.

Le parcours automatique est complet : **11 fichiers validés, aucun échec**.
Whisper Small contrôle les prises ; un second modèle local, Whisper Medium,
arbitre ses refus et vérifie systématiquement chaque fichier final. Les tons
approuvés et les critères de contrôle restent inchangés. Le modèle est déjà
installé sur ce PC ; sa préparation sur un autre PC et la reprise sont décrites
dans le guide. Lancer **Ecouter_Roi_Grenouille_Automatique.cmd** pour écouter.
L'audit des onze fichiers se relance avec
`python -m tools.audit_automatic_audio`.

La méthode complète pour le prochain conte est conservée dans
[le guide de création et de génération](docs/creation_conte_audio.md), avec
les consignes de projet dans `AGENTS.md`.

## Choisir le conte ou le livre

**Nouveau : Le roi-grenouille ou Henri-le-Ferré.** À l'accueil, choisir
**Ouvrir le Roi-grenouille**, ou lancer `Essayer_Roi_Grenouille.cmd`.
Le conte des pages 14-15 du recueil Grimm est conservé presque mot pour mot,
à la troisième personne, avec 10 décisions et 11 passages. Seul son premier
segment est produit en audio, avec les tons approuvés de la série 3 et une
seconde de silence initial. [Guide du conte](docs/roi_grenouille.md) ·
[Lecture complète avec les choix](docs/lecture_roi_grenouille.md).

**Double-cliquer sur `Lancer.cmd`.** L'accueil permet désormais d'ouvrir
**La Maison aux Sept Cages** ou **La petite passeuse d'étoile**, le roman
d'Edouard Bonguet. **Ouvrir le livre** affiche directement le premier passage.
Le menu **Aventure → Choisir une histoire** revient à cet accueil.

Le livre propose le **premier chapitre complet** : 27 décisions, exactement
deux possibilités par décision, et 28 illustrations réalistes en noir et blanc,
une par passage. La narration reste à la troisième personne, au passé, avec
la question **« Que doit choisir Alex ? »**. Le texte a été repris directement
du PDF présent à la racine, en conservant davantage ses phrases, ses images et
la continuité de ses paragraphes. Les choix modifient ses actions et certaines
difficultés plus tard dans le chapitre : une observation peut faciliter une
traversée, une précipitation laisser une blessure. Les événements et l'ordre
du roman sont conservés. Les illustrations sont placées au-dessus
du texte et leur taille a été réduite ; l'ensemble défile et les deux boutons
restent visibles en bas. La lecture est estimée à environ 52 à 53 minutes
à 150 mots/minute, réflexion et lecture des choix comprises. Elle reste libre.

Le chapitre 2 n'est pas encore adapté. Le conte garde ses parcours existants.
Les images et les textes fonctionnent hors ligne. Le premier passage dispose
déjà d'un audio : **Ouvrir le livre** lance sa lecture automatiquement. Chaque
passage lit ensuite son WAV lorsqu'il existe ; un audio absent laisse lire le
texte normalement. Les fichiers produits par `generer_audio_chapitre1.py` sont
reconnus directement, sans copie supplémentaire.
Les boutons **Lecture**, **Pause** et **Rejouer** à côté de l'image permettent
de contrôler le son. La lecture commence par 800 ms de silence, réglables dans
`config.json` (`audio_lead_in_ms`). Aucun audio ne doit être régénéré pour en profiter.

[Guide du premier chapitre](docs/passeuse_chapitre1.md) ·
[Parcours de lecture](docs/lecture_passeuse_ch1.md) ·
[Images et prompts de génération](docs/illustrations_passeuse_ch1.md).

Le manuscrit du chapitre se corrige dans `content/authored/books/passeuse_ch1.json`.
Pour reconstruire les textes après une correction éditoriale :
`python -m tools.author_passeuse`. L'audit du chapitre s'exécute avec
`python -m tools.audit_passeuse` (Pillow requis uniquement pour cet audit).

Moteur de contes fantastiques interactifs pour 9–13 ans. Application PC Python,
entièrement hors ligne, avec textes locaux, douze décisions et deux choix à chaque
décision. Aucun modèle IA ni appel réseau ne s'exécute pendant une partie.
Le nouveau pilote, **La Maison aux Sept Cages**, rejoint les six récits existants.
Il développe un sauvetage inspiré des Grimm, avec trois trames et des animaux
dotés de caractères distincts.

## Essayer le conte pilote

**Double-cliquer sur `Essayer_Sept_Cages.cmd`.** Choisir un héros, un lieu et un
objet, puis commencer. Ce lanceur garde le même conte en mode normal, sans debug.
Le résultat d'un choix ouvre directement le passage suivant.

À la fin, « Une nouvelle aventure » permet de rejouer. Les trois premières
parties dans la même fenêtre proposent chacune une trame différente ; ensuite,
la trame change à nouveau entre deux parties. Les décisions modifient les aides,
le chemin, le sauvetage et la conclusion. [Guide du pilote](docs/conte_pilote_sept_cages.md).

Le pilote a reçu une reprise du rythme, des dialogues et des transitions.
Un [parcours de lecture](docs/lecture_pilote_sept_cages.md) montre la nouvelle
version. Le [mémo éditorial](docs/memo_editorial_contes.md) conserve les retours
et les améliorations à reprendre pour les prochains contes. Après une mise à
jour des textes, fermer puis relancer le jeu pour charger la nouvelle version.

## Jouer sur ce PC

**Double-cliquer sur `Lancer.cmd`.** Le lanceur utilise le Python fourni avec Codex
sur ce PC, une installation locale `.venv` si elle existe, sinon `py -3`.
Choisir une proposition dans chacune des trois catégories, puis « Commencer
l'aventure ». Les touches 1/2, A/B ou gauche/droite correspondent aux deux boutons.
Pour les six anciens contes, lire la conséquence, puis cliquer sur « Poursuivre ».
Dans le pilote, cette conséquence est intégrée au passage suivant. Le texte se fait défiler
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

Sept familles, 144 scènes préparées et cinq conclusions par famille :

Il y a **sept intrigues principales**. Chacune accepte les 125 combinaisons de
héros, lieu et objet, soit 875 configurations de départ au total. Les personnages,
révélations, décisions, résultats et conclusions apportent d'autres variations.
Ces versions partagent une intrigue reconnaissable et plusieurs scènes communes.

| Aventure | Sujet |
| --- | --- |
| La Couronne d'Aubépine | Une couronne volée, une poursuite et un repaire de bandits |
| Le Dragon et la Source | Un dragon enchaîné et une source à rendre au village |
| Les Dormeurs de Roncelune | Un domaine endormi, des ronces et un contre-sort |
| Lume et les Braconniers | Un jeune griffon capturé et son retour auprès des siens |
| La Fleur de Guérison | Un remède à rapporter après les épreuves d'une fée |
| Les Digues de Clairval | Une crue, une vanne sabotée et un village à protéger |
| La Maison aux Sept Cages | Retrouver Lison, délivrer des enfants changés en oiseaux et tenir ses promesses |

Les six anciens contes contiennent **environ 196 minutes de prose distincte**, variantes et résultats
compris, donc davantage que les 120 minutes initialement visées. Ce nombre compte
les blocs écrits distincts une seule fois, sans multiplier les 125 substitutions.
Une partie n'utilise qu'une petite fraction des variantes.

**Audit précédent des six contes : 10 000 simulations, moyenne 21,15 minutes ; minimum 20,59 ; maximum 21,61.**
Toutes atteignent une conclusion avec douze décisions. L'audit des chemins, qui
prend une enveloppe conservative des variantes, donne environ 20,05 à 21,8 minutes.
Ces valeurs sont des estimations à **150 mots/minute et 10 secondes de réflexion
par choix**, question et possibilités parlées comprises, réglables dans `config.json`. L'application laisse lire à son rythme :
elle n'impose pas vingt minutes d'attente. Chronométrer de vrais essais, puis les
futurs WAV, reste nécessaire pour vérifier la durée réellement vécue.

**Pilote, reprise lyrique : 3 000 simulations, environ vingt minutes par partie.**
Toutes les scènes et les cinq conclusions sont atteintes. Les rapports du pilote
sont `reports/validation_reprise_lyrique_cages.json` et
`reports/simulation_reprise_lyrique_cages_3000.json`.

Les rapports précédents sont dans `reports/validation.json`,
`reports/simulation_10000.json` et `reports/configurations_125.json`.
La précédente version des récits est conservée dans `archives/v1-contenu-2026-10-03`.
Les nouveaux journaux sont au format V2 ; les anciens correspondent au contenu archivé.
Pour lire un exemple complet de chacun des nouveaux contes, ouvrir
[les six lectures](docs/lecture_des_six_contes.md). Elles sont exportées par
`tools.export_reading_examples`, avec un parcours déterminé par conte.

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

Les tests jouent **125 trios × 7 arcs × 2 parcours = 1 750 aventures**.
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
avec le lecteur MCI de Windows et `aplay` s'il est disponible sur Linux.
Un fichier absent laisse simplement le texte affiché. Aucun TTS ne s'exécute.

```powershell
py -3 -m tools.export_tts_manifest --output reports/tts_manifest.jsonl
py -3 -m tools.export_tts_manifest --session chemin_vers_le_journal.json --output reports/tts_une_partie.jsonl
py -3 -m tools.verify_tts_coverage reports/tts_manifest.jsonl
```

Le manifeste exporte la narration complète, puis **« Que fais-tu ? Choix 1 : …
Ou choix 2 : … » dans le même segment de chaque décision**. La question et les
deux possibilités seront donc lues à la fin du WAV. Les six anciens contes ont des
conséquences séparées et utilisent 26 segments par partie. Le pilote utilise
14 segments : chaque conséquence ouvre la narration suivante. Le hash identifie tout le texte
parlé, choix compris. Le PC lit déjà ce WAV complet et les conséquences disponibles.

Le lot précédent des six contes contient **6 342 segments**, pour **1 299 passages distincts** avec
le découpage par défaut. Les WAV complets représentent environ **22,4 Gio** de
PCM24k, avec des paragraphes communs répétés dans leurs variantes. Le cache évite
de synthétiser plusieurs fois ces paragraphes. Le manifeste est une enveloppe
des états et peut inclure des variantes conservatrices.

Pour préparer uniquement le pilote, sans produire d'audio :

```powershell
py -3 -m tools.export_tts_manifest --arc cages --output reports/tts_cages.jsonl
```

Pour la Passeuse, le [script de génération du chapitre 1](docs/generation_audio_chapitre1.md)
produit tous les textes accessibles, avec leurs variantes de choix, en blocs de
300 caractères maximum avec 150 ms de pause. Il conserve le premier segment
validé et les blocs communs, avec reprise automatique :

```powershell
.\.venv-tts\Scripts\python.exe -u .\generer_audio_chapitre1.py
```

Pour **La Maison aux Sept Cages**, le [script dédié](docs/generation_audio_sept_cages.md)
reprend la même voix et les réglages de la Passeuse. Il prépare les textes
accessibles des trois trames et les variantes de héros, lieu, objet et choix.
Les WAV sont écrits dans `audio/files`, directement reconnus par l'application :

```powershell
.\.venv-tts\Scripts\python.exe -u .\generer_audio_sept_cages.py
```

Ajouter `--dry-run` pour voir le plan sans génération, ou `--limit 1` pour
commencer par un seul WAV. Relancer la même commande reprend le lot.

Le [guide Chatterbox V3](docs/chatterbox_v3.md) explique l'installation séparée,
l'échantillon de ta voix, le premier lot et la production complète. Après installation :

```powershell
.\.venv-tts\Scripts\python.exe -m tools.generate_audio --dry-run
.\.venv-tts\Scripts\python.exe -m tools.generate_audio --voice audio\reference\ma_voix.wav --scene lantern_1 --limit 6
.\.venv-tts\Scripts\python.exe -m tools.generate_audio --voice audio\reference\ma_voix.wav
.\.venv-tts\Scripts\python.exe -m tools.audit_audio --manifest reports\tts_manifest.jsonl
```

**Après un plantage, relancer la même commande.** Les WAV terminés sont vérifiés
et conservés, les passages déjà synthétisés restent en cache et les segments
manquants sont repris. Les fichiers partiels ne comptent pas comme terminés.
Le script écrit progressivement les reçus et le journal ; il protège les sorties
avec un verrou système. Changer de voix ou de réglages demande un dossier séparé
ou l'option explicite `--overwrite`.

La production vérifie aussi les **paroles avec faster-whisper** : comparaison
au texte, contrôle des derniers mots et des annonces des choix. Un passage coupé
est retenté avec une nouvelle graine, puis raccourci si nécessaire. Un passage
qui échoue encore reste à revoir et ne produit pas de WAV final validé.
`--attempts 5` augmente le nombre d'essais ; `--asr-model medium` change le
contrôleur sans refaire les voix déjà correctes. L'audit distingue désormais un
WAV lisible d'un WAV dont les paroles ont été contrôlées.

Les tests de reprise utilisent un synthétiseur de test. La production Chatterbox
réelle et la ressemblance à ta voix restent à vérifier avec ton échantillon.

## Architecture et ajout de contenu

```text
main_pc.py / Lancer.cmd   Application Tkinter
main_pi.py               Fabrique du même moteur ; point d'entrée GPIO à compléter
engine/                  État, règles, probabilités, transitions, validation, simulation
ui/                      Interface PC
audio/                   Lecteur local et outils de production vocale séparés
content/                 Catalogues, contrat JSON, arcs et scènes locaux
content/authored/        Sources éditoriales des contes
tools/                   Compilation, validation, simulation et production TTS reprenable
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
