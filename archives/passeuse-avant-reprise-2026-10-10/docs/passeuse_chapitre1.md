# Essayer La petite passeuse d'étoile

Double-cliquer sur **Lancer.cmd**, puis choisir **Ouvrir le livre** et
**Commencer le chapitre**. On joue Alex, le personnage du roman d'Edouard Bonguet.
Le menu **Aventure → Choisir une histoire** permet aussi de retrouver le conte.

Le premier chapitre du PDF, pages 5 à 19, est adapté jusqu'à la sortie de la
rivière, de l'autre côté du mur. Il comprend **27 décisions et 28 passages**.
Chaque décision offre deux possibilités. L'effet du choix apparaît au début
du passage suivant ; quelques observations reviennent aussi plus tard.

Les événements essentiels et leur ordre sont conservés : le réveil dans la
chambre, les neuf étages, l'enseignement du bonheur imposé, les files surveillées,
le travail du bois et la notation, les petites voitures, les pauses et les
silences, les escapades sur le toit, le caillou, la peur, l'arrivée des trois
sentinelles, la fuite, les rues copiées, la cave, la grue, le regard sur la foule,
la rivière, la grille et la racine. La perspective passe de la troisième à la
deuxième personne pour que le lecteur habite les pensées et les gestes d'Alex.

Les choix ouvrent de petites variations qui rejoignent la trame principale.
Ils ne créent pas des versions contradictoires du destin d'Alex. Le lecteur
décide notamment ce qu'elle observe, comment elle se déplace et sur quoi elle
prend appui dans l'urgence. On conserve les sentiments parfois contradictoires
du texte : ennui, peur, regret de la sécurité perdue, solitude et désir de liberté.

Les passages avant une décision contiennent environ **158 à 223 mots**,
conséquence précédente comprise, pour une moyenne de **198 mots**. Le conte
pilote se situe souvent autour de 150 à 200 mots. Le chapitre est plus long au
total parce qu'il garde l'ensemble de sa progression. L'estimation est de
**45 minutes** à 150 mots/minute, en comptant la lecture des possibilités et
dix secondes de réflexion par choix. Aucun délai n'est imposé dans l'application.

Une illustration accompagne chaque passage dans le panneau de lecture.
Les touches **1/2**, **A/B** et **gauche/droite** fonctionnent comme les boutons.
Le texte défile ; les choix restent visibles. À la fin, on peut rejouer le
chapitre ou choisir une autre histoire. Le chapitre 2 est annoncé comme à venir.

La génération a utilisé l'outil intégré **ImageGen**. Les illustrations finales
sont conservées dans `D:\livre_heros\images\passeuse\` ;
les [prompts complets et fichiers correspondants](illustrations_passeuse_ch1.md)
permettent de reprendre leur direction artistique. Aucun service IA ni réseau
n'est utilisé pendant la lecture. L'application conserve sa dépendance unique
à Python et Tkinter. Le livre n'a pas encore de narration audio.

## Relire ou corriger

- [Lire un parcours complet](lecture_passeuse_ch1.md).
- Source éditoriale : `tools/author_passeuse.py`.
- Contenu lu par le jeu : `content/books/passeuse_ch1.json`.
- Moteur des chapitres : `engine/book_engine.py`.
- Rapport : `reports/passeuse/validation.json`.

Après modification du manuscrit, exécuter `python -m tools.author_passeuse`,
puis fermer et relancer le jeu. L'audit `python -m tools.audit_passeuse` exporte
une lecture et contrôle 2 000 parcours variés, les transitions et les images.
Les tests de `tests/test_passeuse.py` vérifient aussi les conséquences, les
souvenirs, les journaux et le passage entre les deux histoires dans l'interface.

Pour enregistrer et rejouer un parcours, activer **Outils → Mode debug**, puis
utiliser les commandes de journal déjà présentes. Les journaux du livre ont
leur propre format et sont détectés automatiquement ; les journaux des contes
restent compatibles avec leurs textes actuels.

Cette vérification technique permet de livrer un essai jouable. Le rythme,
l'intérêt des petits choix et la fidélité de la voix restent à apprécier lors
de la lecture de l'auteur, avant de poursuivre l'adaptation du roman.
