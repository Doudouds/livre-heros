# Essayer La petite passeuse d'étoile

Double-cliquer sur **Lancer.cmd**, puis choisir **Ouvrir le livre** :
le premier passage s'affiche directement. Le lecteur accompagne Alex, le personnage du roman
d'Edouard Bonguet, et décide de ses actions à chaque étape.
Le menu **Aventure → Choisir une histoire** permet aussi de retrouver le conte.

Le premier chapitre du PDF, pages 5 à 19, est adapté jusqu'à la sortie de la
rivière, de l'autre côté du mur. Il comprend **27 décisions et 28 passages**.
Chaque décision offre deux possibilités sous la question **« Que doit choisir
Alex ? »**. L'effet du choix apparaît au début du passage suivant et peut modifier
des actions ou des difficultés plusieurs passages plus loin.

Les événements essentiels et leur ordre sont conservés : le réveil dans la
chambre, les neuf étages, l'enseignement du bonheur imposé, les files surveillées,
le travail du bois et la notation, les petites voitures, les pauses et les
silences, les escapades sur le toit, le caillou, la peur, l'arrivée des trois
sentinelles, la fuite, les rues copiées, la cave, la grue, le regard sur la foule,
la rivière, la grille et la racine. La reprise du 10 octobre 2026 s'appuie
directement sur le PDF ajouté à la racine du projet. La narration reste à la
troisième personne et au passé, comme dans le roman.

La reprise lyrique conserve davantage les phrases et les paragraphes du livre.
L'âge et les années écoulées depuis l'enseignement restent dans le même mouvement
de phrase, suivis des leçons d'histoire et de leur définition du bonheur. Les
images du texte — l'heureuse marionnette, les pensées vagabondes, les colonnes
vivantes — sont conservées. Les raccords et les conséquences ont été réécrits
pour prolonger ces passages et éviter les reprises d'actions déjà accomplies.

La reprise des 28 passages, des 49 variantes et de toutes les conséquences
réserve les ajouts aux décisions et à leurs effets. Les gestes ont une
intention liée à la scène ; les variations portent sur l'attente, la
surveillance, la fatigue, la douleur et les observations retenues. La
proximité des sentinelles fait craindre un écart sous leurs yeux rouges,
sans inventer un danger pour les mains près des roues. Les images lyriques
du roman restent présentes, et les formulations qui répétaient les deux
options affichées ont été allégées. Les raccords ont aussi été relus dans
des parcours continus, jusqu'à la sortie de la rivière.

Les explications nécessaires aux choix précèdent leur première utilisation.
Le passage 5 présente le tapis roulant, les tiges qui examinent les pièces,
la notation et les récompenses ou remontrances. Les précisions de lieu
distinguent aussi la grille de ventilation, la porte de l'escalier et la
grille qui barre la rivière sous le mur.

Les choix ouvrent de petites variations qui rejoignent la trame principale.
Ils ne créent pas des versions contradictoires du destin d'Alex. Le lecteur
décide notamment ce qu'elle observe, comment elle se déplace et sur quoi elle
prend appui dans l'urgence. Observer les sentinelles permet de traverser une rue
sans devoir se cacher à nouveau ; négliger une encoche entraîne une remontrance.
Une fuite précipitée peut lui faire heurter le genou, ce qui complique ensuite
la grue et la sortie de l'eau. Ces détails sont des variations de l'adaptation.
Les sentiments du texte sont conservés : ennui, peur, regret de la sécurité
perdue, solitude et désir de liberté.

Les passages avant une décision contiennent environ **172 à 331 mots**,
conséquence précédente comprise, pour une moyenne de **238 mots**. Le conte
pilote se situe souvent autour de 150 à 200 mots. Le chapitre est plus long au
total parce qu'il garde l'ensemble de sa progression. Certains paragraphes
restent plus longs pour conserver une réflexion complète. L'estimation est de
**52 à 53 minutes** à 150 mots/minute, en comptant la lecture des possibilités et
dix secondes de réflexion par choix. Aucun délai n'est imposé dans l'application.

Une illustration apparaît **au-dessus du texte** de chaque passage.
Sa taille a été réduite : 512 pixels de large dans une fenêtre de 1100 × 800,
384 pixels dans une fenêtre de 800 × 620. L'image et le texte défilent
ensemble dans la zone de lecture.
Les touches **1/2**, **A/B** et **gauche/droite** fonctionnent comme les boutons.
Les deux boutons de choix restent visibles en bas. À la fin, on peut rejouer le
chapitre ou choisir une autre histoire. Le chapitre 2 est annoncé comme à venir.

La génération a utilisé l'outil intégré **ImageGen**. Les illustrations finales
sont conservées dans `D:\livre_heros\images\passeuse\` ;
les [prompts complets et fichiers correspondants](illustrations_passeuse_ch1.md)
permettent de reprendre leur direction artistique. Aucun service IA ni réseau
n'est utilisé pendant la lecture. L'application conserve sa dépendance unique
à Python et Tkinter. Le livre n'a pas encore de narration audio.

## Relire ou corriger

- [Lire un parcours complet](lecture_passeuse_ch1.md).
- Manuscrit éditorial : `content/authored/books/passeuse_ch1.json`.
- Compilation du manuscrit : `tools/author_passeuse.py`.
- Contenu lu par le jeu : `content/books/passeuse_ch1.json`.
- Moteur des chapitres : `engine/book_engine.py`.
- Rapport : `reports/passeuse/validation.json`.

Après modification du JSON éditorial, exécuter `python -m tools.author_passeuse`,
puis fermer et relancer le jeu. L'audit `python -m tools.audit_passeuse` exporte
une lecture et contrôle 2 000 parcours variés, les transitions et les images.
Les tests de `tests/test_passeuse.py` vérifient aussi la troisième personne,
les conséquences persistantes, les journaux, la position et la taille des images,
ainsi que le passage entre les deux histoires dans l'interface.

Pour enregistrer et rejouer un parcours, activer **Outils → Mode debug**, puis
utiliser les commandes de journal déjà présentes. Les journaux du livre ont
leur propre format et sont détectés automatiquement ; les journaux des contes
restent compatibles avec leurs textes actuels. Un journal du livre enregistré
avant la reprise du texte est signalé comme incompatible avec cette version.

Cette vérification technique permet de livrer un essai jouable. Le rythme,
l'intérêt des petits choix et la fidélité de la voix restent à apprécier lors
de la lecture de l'auteur, avant de poursuivre l'adaptation du roman.
