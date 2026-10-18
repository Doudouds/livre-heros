# La Maison aux Sept Cages — pilote jouable

Lancer `Essayer_Sept_Cages.cmd`, sélectionner un héros, un lieu et un objet, puis
commencer. À la fin, « Une nouvelle aventure » propose une autre trame. Les trois
premières parties dans la même fenêtre parcourent les trois trames dans un ordre
aléatoire. Fermer la fenêtre réinitialise cette rotation.

Le conte compte douze décisions et deux choix à chaque décision. La conséquence
ouvre directement le passage suivant, sans écran « Poursuivre ». L'estimation de
durée est d'environ vingt minutes ; la lecture reste libre.

Le [script audio du conte](generation_audio_sept_cages.md) génère les passages
avec la même voix que la Passeuse, en blocs de 300 caractères. Les WAV sont
lus automatiquement lorsqu'ils existent ; le récit reste jouable sans eux.

## Écriture et personnages

Maître Renard protège sa dignité, connaît les pièges et préfère les passages
cachés. Une patte blessée limite son aide. Maître Merle parle en vers, aime être
écouté et sait reconnaître les voix. Madame Souris est polie, prudente et veille
sur ses trois petits : promettre de les accueillir engage une action au retour.
Lison invente des fins de chansons ; elle répond aux signaux, guette et participe
au sauvetage dès qu'elle le peut.

La relecture du 4 octobre explicite le départ à la recherche de Lison,
l'identification de son panier et les déplacements entre les scènes. Le refrain
familial, repris le 11 octobre, est « Prends ma main, je rentre avec toi ». Lison
prend ta main en le chantant dès l'ouverture ; sa reconnaissance repose sur ce
qui a été présenté au lecteur. Les résultats des approches décrivent désormais
des actions propres à chaque trame.

La reprise suivante travaille le rythme et les voix : Lison répond à la sorcière,
la visiteuse marchande à la porte, Madame Souris explique le sort dans un échange.
Des silences, des hésitations et des sensations liées à l'enjeu remplacent
plusieurs résumés d'actions. Le sauvetage et les retrouvailles donnent davantage
de place aux paroles des enfants. [Lire un parcours avec la visiteuse](lecture_pilote_sept_cages.md).

Le [mémo éditorial](memo_editorial_contes.md) rassemble tous les retours reçus,
les corrections réalisées, les principes pour les prochains contes et les
décisions encore ouvertes. Les trois sélections initiales sont notamment
conservées : leur simplification reste une proposition.

La transformation est montrée au joueur. Le refrain de Lison et le signal de
cache-cache permettent ensuite de la reconnaître. Madame Souris rapporte avoir
vu un autre prisonnier retrouver sa forme quand sa cage est ouverte avec la clef
d'argent. Briser un barreau libère un oiseau sans défaire l'enchantement.

## Parcours et conséquences

Les trois trames partagent la disparition et la découverte du sort. Le milieu
change : maison au soir, arrivée d'une visiteuse voulant acheter un chanteur, ou
départ de la sorcière avec ses cages sur un chariot. Chaque situation a ses
approches et ses scènes pour obtenir la clef. Une capture oblige à modifier le
plan tout en conservant l'objectif et les douze décisions.

Les cinq conclusions suivent les faits : tous les enfants délivrés, Lison seule
redevenue humaine, Lison ramenée sous forme d'oiseau, six enfants délivrés avec
Lison encore captive, ou retour sans prisonnier libéré. La promesse à la souris
et l'aide apportée au renard reparaissent dans la conclusion.

## Sources et vérification

Les motifs viennent des lectures directes de Grimm décrites dans
[la proposition](proposition_conte_pilote_grimm.md), en particulier *Jorinde et
Joringel*, *La reine des abeilles* et *Les musiciens de Brême*. Le conte, ses
dialogues et ses parcours sont nouveaux.

Les textes et règles sont dans `content/authored/cages.json` ; les versions lues
par le jeu sont `content/arcs/cages.json` et `content/scenes/cages.json`.
`tools.author_cages` contient le manuscrit préparatoire et réécrit ces trois
fichiers. `tools.build_content` accepte ce graphe déjà écrit sans ajouter les
insertions des anciens contes. Les six anciens récits sont conservés.

Les tests couvrent les 125 configurations, les parcours, les issues extrêmes,
les états du sauvetage, la promesse, la reproduction des journaux, les identifiants
audio et l'interface. Le rapport de relecture est
`reports/validation_reprise_lyrique_cages.json`. Les 3 000 simulations de cette
reprise atteignent les trente scènes et les cinq conclusions, sans sortie des
bornes de durée. Les résultats sont dans
`reports/simulation_reprise_lyrique_cages_3000.json` ; les trente tests du moteur,
du pilote et de l'interface sont dans `reports/tests_reprise_lyrique_cages.txt`.
Ces contrôles vérifient le fonctionnement ; l'essai du lecteur permettra de
juger le rythme et la justesse des dialogues.

L'export vocal d'une partie produit quatorze narrations, conséquences et choix
inclus. Le manifeste global du pilote peut être préparé avec :

```powershell
py -3 -m tools.export_tts_manifest --arc cages --output reports/tts_cages.jsonl
```

Cet export prépare du texte et des chemins de WAV ; il ne synthétise pas la voix.
