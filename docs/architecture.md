# Architecture et contrat narratif V2

Le moteur utilise uniquement la bibliothèque standard Python (3.10 ou ultérieur).
Les textes, règles, rencontres et transitions sont des données JSON locales. Aucun
service réseau, modèle IA, compte ni sauvegarde permanente du héros n'intervient.

## Graphe et déroulement

Un arc contient une introduction, douze rangs de décision et plusieurs conclusions.
Chaque décision contient exactement deux choix. Chaque choix possède trois sorties
(`success`, `complication`, `failure`) avec un texte, des effets et une destination.
Plusieurs scènes d'un même rang peuvent représenter des branches ; elles rejoignent
ensuite une scène commune. Les destinations doivent avancer d'un rang : le graphe
est fini, et les échecs n'écourtent jamais une aventure.

Une scène comprend `id`, `kind` (`intro`, `decision`, `ending`), `act`, `rank`,
`title`, `text`, `variants`, `conditions`, `effects`, `audio_file`, et selon son type
`next`, `choices` ou `ending`. Les variantes ont des conditions et peuvent ajouter
du texte, remplacer le texte ou remplacer les deux choix. Les champs de texte
acceptent seulement les clés documentées dans `content/catalog.json` et les trois
catalogues de paramètres. Chaque arc peut préciser `item_overrides` pour adapter
les trois usages de l'objet aux obstacles réels de sa quête. La substitution ne
peut pas exécuter de code.

Les conditions sont des objets sans expression Python : `all`, `any`, `not`,
`hero`, `item`, `location`, `flag`, `ally`, `inventory`, `min_success`, `min_failure`,
`min_complication`. Les effets autorisés sont `set_flags`, `unset_flags`,
`add_allies`, `remove_allies`, `add_inventory`, `remove_inventory`,
`visit_locations`, `meet_characters`, `add_enemies`, `events`.

Chaque choix définit `id`, `text`, `base_success`, `complication_share`,
`modifiers` et `outcomes`. Chaque modificateur a `label`, `when`, `delta`.
`base_success` est la probabilité d'atteindre l'objectif, complication comprise.
La probabilité finale est bornée entre 0,35 et 0,90. Avec un tirage uniforme `r` :
réussite si `r < p × (1 − complication_share)`, complication si `r < p`,
sinon échec. Une complication atteint donc l'objectif et en paie un prix narratif.
Les modificateurs, seuils et tirages sont enregistrés, mais jamais affichés au joueur.

## Variété et mémoire

Un générateur `random.Random(seed)` par partie décide de l'arc, de la rencontre,
de la révélation, des variantes et des résultats. Le journal contient la graine,
la configuration, l'arc et les choix ; le rejouer reproduit textes et tirages.
Une nouvelle instance de `StoryEngine` crée un `StoryState` entièrement neuf.
Les conséquences demeurent dans les flags et les alliés, influencent les scènes
de raccord, le climax et le choix de la conclusion.

## Durée

Les estimations dérivent du texte réellement assemblé, y compris les résultats,
et les deux choix introduits à voix haute, à 150 mots par minute, plus
10 secondes de réflexion par décision. Elles ne sont
pas un chronomètre qui force le lecteur à attendre. Le validateur calcule les
bornes des chemins pour les 125 configurations et chaque arc. Le simulateur
mesure les chemins réellement produits. L'oral humain et la réflexion réelle
devront être chronométrés lors des essais : 18–22 minutes est une cible estimée.

## Frontières matérielles

`StoryEngine` n'importe jamais Tkinter, un lecteur audio ou GPIO.
`InputBackend`, `DisplayBackend` et `AudioPlayer` sont des interfaces distinctes.
La première livraison utilise Tkinter ; `main_pi.py` prépare le point d'entrée
sans prétendre avoir livré le câblage GPIO. Les deux boutons futurs correspondent
à `choose(0)` et `choose(1)` ; les broches restent configurables et non attribuées.

L'export TTS produit des segments complets après substitution, indexés par un
hash du texte. Les chemins audio associés sont donc spécifiques au texte entendu,
pas seulement à un ID de scène susceptible d'avoir plusieurs versions. Les fichiers
WAV sont facultatifs. Le texte parlé d'une décision contient sa narration puis
« Que fais-tu ? Choix 1 : … Ou choix 2 : … ». Son hash porte sur l'ensemble.
Le journal V2 conserve `spoken_text` et les nouvelles durées. Un ancien journal
V1 doit être rejoué avec le contenu archivé correspondant.

Le lecteur PC utilise les commandes MCI de Windows pour suspendre et reprendre
le WAV à la même position, ou revenir au début. Le silence initial configurable
(`audio_lead_in_ms`, 800 ms par défaut) est ajouté à une copie de lecture PCM
dans `tmp/audio_playback`. Cette copie est réutilisée tant que le fichier source
et le réglage n'ont pas changé ; les sorties TTS et leurs reçus restent intacts.
Les commandes WAV sont documentées par
[Microsoft](https://learn.microsoft.com/en-us/windows/win32/multimedia/waveform-audio-command-set).
Les boutons désactivés signalent un audio absent ou illisible, sans bloquer le récit.

`tools/generate_audio.py` est un outil de préparation distinct. Il utilise
Chatterbox Multilingual V3 sur PC, un cache de passages, des reçus vérifiables et
des écritures atomiques. Le jeu n'importe pas cet adaptateur. Les longs WAV
finaux sont assemblés à partir du cache ; les questions restent à leur fin.
`tools/audit_audio.py` contrôle la production et mesure les durées réelles des WAV.

`audio/speech_verification.py` retranscrit chaque passage avec faster-whisper
local, puis compare le texte, la fin et les annonces des choix. Ce contrôle est
distinct de la validation PCM et de l'empreinte du fichier. Les reçus conservent
sa preuve et sa politique. Une nouvelle politique peut revalider le cache de
voix existant. Les prises suspectes sont retentées avec des graines différentes,
puis découpées plus court ; les échecs restent hors des WAV finaux approuvés.

`content/schema.json` décrit le format structurel. `engine/validator.py` ajoute les
contraintes du graphe, des règles, du contenu et de compatibilité.
