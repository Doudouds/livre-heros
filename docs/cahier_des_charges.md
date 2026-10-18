# Cahier des charges — Moteur de contes fantastiques interactifs

## 1. Objectif du projet

Développer un moteur de contes interactifs de type **« livre dont vous êtes le héros »**, destiné principalement à des **pré-adolescents**.

L'expérience finale fonctionnera sur un **Raspberry Pi Zero 2 W**, entièrement hors ligne et sans intelligence artificielle exécutée sur le Raspberry Pi.

L'intelligence artificielle peut être utilisée pendant le développement pour créer les arcs narratifs, textes, variantes et ressources. En revanche, lors de l'utilisation finale, toutes les histoires doivent être produites par un moteur procédural déterministe/probabiliste utilisant des contenus préparés à l'avance.

La narration sera à terme entièrement audio. Les voix seront générées séparément avec **Chatterbox v3**. La génération des fichiers audio n'est pas demandée dans la première phase du projet.

La première livraison doit obligatoirement être une **version PC fonctionnelle**, permettant de tester en profondeur le moteur narratif avant son portage sur Raspberry Pi Zero 2 W.

---

# 2. Public et univers

Public principal :

**pré-adolescents**, environ 9 à 13 ans.

Le ton doit être :

- aventureux ;
- fantastique ;
- immersif ;
- accessible sans être infantile ;
- parfois mystérieux ou inquiétant ;
- jamais horrifique ou graphiquement violent ;
- capable de comporter du danger, des enjeux et des échecs sans devenir traumatisant.

L'univers général est celui de la fantasy :

châteaux, magie, dragons, créatures fantastiques, ruines, royaumes, artefacts, forêts enchantées, cités mystérieuses, montagnes, passages secrets, sortilèges, etc.

Les histoires doivent accorder la même place aux personnages masculins et féminins.

Aucun rôle narratif ne doit être implicitement réservé à un sexe.

Chevalerie, magie, exploration, ruse, commandement, courage, soin, érudition ou combat doivent être accessibles indifféremment aux garçons et aux filles.

---

# 3. Principe fondamental : le joueur est le héros

L'utilisateur est directement le protagoniste.

La narration doit donc employer principalement la **deuxième personne** :

> Tu avances jusqu'à l'entrée du château…

> Derrière toi, quelque chose vient de bouger.

> Tu dois maintenant décider quoi faire.

Éviter autant que possible les formulations nécessitant de connaître le sexe du joueur.

Par exemple, au lieu de répéter :

> Tu es un chevalier / une chevalière…

préférer ensuite :

> Tu as été formé à l'art de la chevalerie.

Cela évite d'ajouter une quatrième question initiale uniquement pour connaître le genre.

---

# 4. Configuration initiale de l'histoire

Avant chaque nouvelle aventure, poser **exactement trois questions**.

Aucune saisie libre.

L'utilisateur choisit parmi cinq propositions prédéfinies pour chaque catégorie.

Cela représente :

5 × 5 × 5 = **125 configurations initiales possibles**.

Ces 125 configurations ne doivent surtout pas conduire à créer 125 histoires entièrement indépendantes.

Le moteur doit utiliser des **arcs narratifs modulaires et adaptatifs**.

## Question 1 — Quel type de héros veux-tu être ?

1. **Chevalier / Chevalière**
   - courage ;
   - discipline ;
   - connaissance du combat et des fortifications.

2. **Apprenti magicien / apprentie magicienne**
   - magie ;
   - connaissance des sorts et phénomènes surnaturels.

3. **Explorateur / Exploratrice**
   - orientation ;
   - observation ;
   - connaissance des endroits dangereux.

4. **Gardien / Gardienne des créatures**
   - compréhension des animaux et créatures fantastiques ;
   - empathie ;
   - capacité à apaiser certaines situations.

5. **Voleur / Voleuse au grand cœur**
   - discrétion ;
   - ruse ;
   - serrures, pièges et passages secrets.

Ces caractéristiques sont **internes au moteur**.

Aucun système de statistiques ne doit être présenté au joueur.

## Question 2 — Quel lieu veux-tu absolument rencontrer dans ton aventure ?

1. **Un château abandonné**
2. **Une forêt enchantée**
3. **La montagne des dragons**
4. **Une cité flottante**
5. **Des ruines souterraines oubliées**

Le lieu choisi doit jouer un rôle important dans l'histoire.

Il ne doit pas simplement être mentionné dans une phrase.

Il doit idéalement accueillir une scène importante, une révélation, un choix ou le climax.

## Question 3 — Quel objet veux-tu posséder ?

1. **Une épée runique**
2. **Un grimoire vivant**
3. **Une amulette de protection**
4. **Une boussole enchantée**
5. **Une clé de cristal**

L'objet choisi doit réellement influencer l'aventure.

Au minimum :

- il doit être mentionné naturellement ;
- il doit intervenir dans plusieurs scènes ;
- il doit modifier au moins une possibilité ou conséquence ;
- il doit pouvoir influencer une probabilité de réussite ou débloquer une variante narrative.

Il ne doit jamais constituer un simple élément décoratif.

---

# 5. Durée d'une aventure

Une partie complète doit durer environ :

**20 minutes**.

Plage acceptable :

**18 à 22 minutes**, choix et narration compris.

Chaque aventure doit comporter environ :

**11 à 13 décisions importantes**.

Chaque décision propose toujours :

**exactement deux choix**.

La narration devra être découpée en segments suffisamment longs pour permettre plus tard une narration audio fluide.

Cible indicative :

**45 à 90 secondes de narration par segment**, selon son importance.

La structure générale doit suivre approximativement :

Introduction → découverte de la quête → premières difficultés → complications → révélations → montée dramatique → climax → conclusion.

Le moteur doit contrôler la progression temporelle.

Il ne doit pas être possible qu'une succession de branches allonge une aventure jusqu'à 40 minutes.

Inversement, un échec ne doit pas permettre de terminer accidentellement l'aventure après seulement 8 minutes.

---

# 6. Les choix

Chaque segment, sauf éventuellement l'introduction et la conclusion finale, conduit à **deux choix**.

Exemple :

> La créature bloque le passage.

> Veux-tu :
>
> A — essayer de lui parler ?
>
> B — chercher un autre passage ?

Les deux choix doivent être raisonnablement attirants.

Éviter les situations du type :

> A — réfléchir intelligemment  
> B — faire quelque chose manifestement stupide

Il ne doit pas exister systématiquement un « bon choix » et un « mauvais choix ».

Les choix peuvent représenter différents styles :

courage, prudence, ruse, empathie, magie, exploration, négociation, prise de risque, etc.

---

# 7. Probabilités cachées

Les probabilités ne doivent **jamais être affichées au joueur**.

Le joueur doit rester plongé dans l'histoire.

Chaque choix possède une probabilité de réussite interne.

Les probabilités peuvent être influencées par :

- le type de héros ;
- l'objet choisi au départ ;
- certaines décisions précédentes ;
- des personnages rencontrés ;
- certains événements précédents ;
- l'état courant du monde.

Exemple interne :

```text
Traverser discrètement le camp :

probabilité de base : 55 %

Voleur au grand cœur : +20 %
Boussole enchantée : aucun effet
A déjà aidé l'éclaireur : +10 %

probabilité finale : 85 %
```

Ne jamais afficher ces calculs hors mode debug.

Les probabilités doivent rester raisonnables. Éviter autant que possible les situations à 5 % ou 100 %.

Plage habituelle recommandée :

**environ 35 % à 90 %** suivant la situation.

---

# 8. Trois catégories de résultat

Un choix ne doit pas conduire uniquement à :

SUCCESS / FAILURE.

Prévoir trois catégories narratives :

### Réussite

L'action atteint son objectif principal.

### Réussite avec complication

Le héros réussit, mais un problème apparaît.

Exemple :

le héros ouvre la porte, mais déclenche une alarme magique.

### Échec avec conséquence

L'action ne fonctionne pas comme prévu, mais l'histoire continue.

Exemple :

le pont s'effondre ; au lieu d'atteindre directement le château, le héros tombe dans une rivière qui mène à des souterrains.

Il faut privilégier le principe :

**« échouer vers l'avant »**.

Un échec doit produire une nouvelle histoire, pas simplement bloquer le joueur.

---

# 9. Pas de Game Over prématuré

Une mauvaise décision ou un mauvais tirage ne doit pratiquement jamais entraîner :

> Tu es mort. Fin.

L'objectif est de raconter une aventure complète.

Les situations dangereuses peuvent conduire à :

- perdre un objet temporairement ;
- découvrir un chemin plus difficile ;
- se faire capturer ;
- déclencher une catastrophe ;
- se séparer d'un allié ;
- devoir réparer une erreur ;
- rendre le climax plus difficile ;
- modifier la conclusion.

Mais l'histoire continue.

---

# 10. État interne de l'aventure

Le moteur doit maintenir un `StoryState`.

Exemples :

```python
hero_type
mandatory_location
chosen_item

current_act
story_progress

visited_locations
met_characters
allies
enemies

flags
inventory
previous_outcomes

success_count
complication_count
failure_count
```

Les informations doivent être entièrement invisibles en mode normal.

Le joueur n'a :

- aucune feuille ;
- aucun carnet ;
- aucun inventaire à gérer manuellement ;
- aucun nombre à mémoriser.

Le moteur se charge de tout.

---

# 11. Aucune mémoire entre deux aventures

Lorsqu'une nouvelle histoire commence, tout l'état narratif précédent est effacé.

Il n'y a pour la première version :

- aucun compte ;
- aucun niveau ;
- aucune progression permanente ;
- aucun personnage conservé entre les parties ;
- aucun inventaire persistant.

Chaque aventure est indépendante.

---

# 12. Architecture narrative

Ne surtout pas construire un arbre intégral où chaque branche se divise continuellement en deux.

Avec douze décisions, cette approche deviendrait rapidement ingérable.

Utiliser plutôt un **graphe narratif**.

Des branches peuvent :

- se séparer ;
- produire différentes conséquences ;
- rejoindre ensuite une scène commune adaptée à l'état précédent.

Une scène commune peut avoir plusieurs variantes.

Exemple :

```text
                 choix A
                /       \
SCÈNE 4 --------         ---- SCÈNE 6
                \       /
                 choix B
```

La SCÈNE 6 doit pouvoir adapter certaines phrases selon ce qui s'est passé auparavant.

Les décisions antérieures doivent néanmoins avoir de vraies conséquences.

---

# 13. Arcs narratifs

Créer plusieurs **grands arcs narratifs maîtres**.

Pour la première version, viser environ **six familles d'aventures** suffisamment différentes pour représenter approximativement deux heures de contenu narratif unique.

Exemples de familles possibles :

- retrouver un artefact disparu ;
- empêcher le réveil d'une ancienne menace ;
- résoudre le mystère d'un royaume ;
- sauver une créature ou un personnage ;
- explorer un endroit interdit ;
- empêcher une catastrophe magique.

Ces exemples ne sont pas des contraintes strictes : créer les arcs les plus intéressants possibles dans l'univers défini.

Chaque arc doit pouvoir intégrer les trois paramètres choisis initialement.

Ne pas écrire :

> arc château + chevalier + épée

puis un autre :

> arc forêt + magicien + amulette.

Créer des arcs suffisamment abstraits et modulaires pour que différentes combinaisons fonctionnent.

---

# 14. Importance réelle des trois choix initiaux

Les trois choix initiaux doivent influencer réellement l'aventure.

Pour chaque partie :

### Le héros choisi

Doit influencer au minimum deux situations, probabilités ou variantes narratives.

### Le lieu choisi

Doit constituer un endroit important de l'histoire.

### L'objet choisi

Doit être utilisé à plusieurs reprises et influencer au moins une décision ou conséquence.

Deux parties utilisant un trio initial différent doivent donc produire une expérience sensiblement différente même si elles utilisent le même arc maître.

---

# 15. Impression d'histoire unique

Il est très important d'éviter l'impression de rejouer simplement le même scénario.

La variété doit provenir simultanément de plusieurs sources :

- trois choix initiaux ;
- choix d'un arc maître ;
- variantes de scènes ;
- personnages secondaires variables ;
- antagonistes différents ;
- rencontres facultatives ;
- résultats probabilistes ;
- conséquences de décisions précédentes ;
- ordre ou sélection de certains événements ;
- plusieurs révélations possibles ;
- différentes formes de climax ;
- plusieurs conclusions.

Il est acceptable que certaines scènes soient réutilisées.

En revanche, une nouvelle partie doit idéalement modifier plusieurs éléments perceptibles.

Ne pas générer les histoires au runtime avec une IA.

Tout le matériel narratif doit être préparé et stocké localement.

---

# 16. Volume de contenu V1

La première base de contenu doit représenter environ :

**120 minutes de narration unique au total**.

Une partie utilisant environ 20 minutes, cette base doit permettre de tester plusieurs aventures nettement différentes.

L'objectif n'est pas encore de produire des centaines d'heures.

Cette V1 sert à valider :

- plaisir de jeu ;
- variété ;
- durée ;
- cohérence ;
- fonctionnement des probabilités ;
- intérêt des choix ;
- impression de rejouabilité.

Concevoir cependant le format de données pour qu'il soit possible d'ajouter ultérieurement beaucoup plus de contenu sans modifier le moteur.

---

# 17. Format des données narratives

Le contenu doit être complètement séparé du moteur Python.

Utiliser de préférence JSON.

Exemple conceptuel :

```json
{
  "id": "forest_bridge_03",
  "arc": "lost_relic",
  "act": 2,
  "text": "Devant toi, le vieux pont disparaît dans la brume...",
  "estimated_duration": 58,

  "conditions": [],

  "choices": [
    {
      "text": "Traverser le pont avec précaution",
      "base_success": 0.70,
      "modifiers": [],
      "success": "bridge_success",
      "complication": "bridge_complication",
      "failure": "river_fall"
    },
    {
      "text": "Chercher un passage sous le pont",
      "base_success": 0.55,
      "modifiers": [],
      "success": "hidden_passage",
      "complication": "creature_encounter",
      "failure": "lost_in_forest"
    }
  ]
}
```

Le schéma réel peut être amélioré si nécessaire.

---

# 18. Validation automatique du graphe

Créer des outils permettant de détecter automatiquement :

- liens vers des scènes inexistantes ;
- scène inaccessible ;
- boucle infinie ;
- choix sans destination ;
- arc sans conclusion ;
- probabilité invalide ;
- combinaison initiale incompatible avec un arc ;
- histoire estimée trop courte ;
- histoire estimée trop longue.

Prévoir également des simulations automatiques de milliers de parties.

Le programme doit pouvoir lancer par exemple :

```text
10 000 aventures simulées
```

sans interface et produire des statistiques :

- durée moyenne ;
- durée minimum/maximum ;
- fréquence des arcs ;
- fréquence des conclusions ;
- nombre moyen de réussites ;
- complications ;
- échecs ;
- scènes les plus/moins utilisées.

---

# 19. Graine aléatoire

Le moteur doit utiliser un générateur pseudo-aléatoire avec possibilité de définir une `seed`.

En utilisation normale :

seed aléatoire.

En debug :

seed choisie manuellement.

Cela doit permettre de reproduire exactement une aventure ayant présenté un problème.

---

# 20. Version PC — première priorité

Avant toute implémentation Raspberry Pi, produire une application PC pleinement fonctionnelle.

Python recommandé.

Interface simple, par exemple avec Tkinter.

Écran initial :

```text
NOUVELLE AVENTURE

1. Choisis ton héros
[...]

2. Choisis ton lieu
[...]

3. Choisis ton objet
[...]

[ COMMENCER ]
```

Pendant l'histoire :

```text
------------------------------------------------

Texte de la scène

------------------------------------------------

[ CHOIX A ]

[ CHOIX B ]

------------------------------------------------
```

Le prototype doit être agréable à tester mais il n'est pas nécessaire de produire une interface graphiquement sophistiquée.

---

# 21. Mode debug PC

Prévoir un mode debug activable.

Il doit pouvoir afficher notamment :

```text
Arc actuel
ID de scène
Acte
Progression estimée
Durée estimée

Choix effectués

Probabilité de réussite réelle
Modificateurs appliqués
Nombre aléatoire tiré
Résultat obtenu

Flags
Inventaire
Alliés
Événements importants

Seed de la partie
```

Le mode normal ne doit montrer aucune de ces informations.

---

# 22. Journal de session

En mode debug, permettre l'enregistrement d'une partie dans un fichier JSON ou texte contenant :

- seed ;
- configuration initiale ;
- scènes parcourues ;
- choix effectués ;
- probabilités ;
- tirages aléatoires ;
- résultats ;
- conclusion.

Cela permettra de transmettre facilement un scénario problématique pour le reproduire.

---

# 23. Audio dans la version PC

La première version doit pouvoir fonctionner **sans fichiers audio**.

Si aucun fichier audio n'est disponible :

afficher simplement le texte.

Prévoir cependant dès maintenant une abstraction :

```python
AudioPlayer
```

Chaque scène doit pouvoir posséder :

```text
audio_file
```

Si le fichier existe :

le lire.

Sinon :

continuer silencieusement avec le texte.

Cela permettra d'ajouter plus tard les fichiers produits par Chatterbox v3 sans changer l'architecture narrative.

---

# 24. Préparation future pour Chatterbox v3

Ne pas effectuer la synthèse vocale dans cette première phase.

Prévoir néanmoins la possibilité d'exporter un manifeste TTS.

Exemple :

```json
{
  "scene_id": "forest_bridge_03",
  "speaker": "narrator",
  "emotion": "mysterious",
  "text": "Devant toi, le vieux pont disparaît dans la brume...",
  "output_file": "audio/forest_bridge_03.wav"
}
```

Les textes destinés à Chatterbox doivent être suffisamment longs pour produire une narration naturelle.

Éviter de fragmenter une scène en dizaines de petits fichiers correspondant à quelques mots.

---

# 25. Portage Raspberry Pi Zero 2 W

La logique narrative PC et Raspberry Pi doit être la même.

Ne pas réécrire le moteur pour le Raspberry Pi.

Séparer les éléments dépendants du matériel :

```text
StoryEngine
    indépendant

InputBackend
    PC : boutons GUI
    Pi : GPIO

AudioBackend
    PC : lecteur PC
    Pi : lecteur audio léger

DisplayBackend
    PC : Tkinter
    Pi : suivant interface finale
```

Le moteur narratif doit rester identique.

La version Raspberry Pi doit être légère et adaptée aux ressources d'un Pi Zero 2 W.

Aucun modèle IA ne sera exécuté dessus.

---

# 26. Commandes physiques futures

Prévoir que les deux choix correspondent à terme à deux boutons physiques :

```text
Bouton gauche  → choix A
Bouton droit   → choix B
```

Ne pas encore imposer de numéros de GPIO.

Ils devront être configurables dans un fichier de configuration.

---

# 27. Structure souhaitée du projet

Proposer une architecture propre, par exemple :

```text
story_engine/
│
├── main_pc.py
├── main_pi.py
│
├── engine/
│   ├── story_engine.py
│   ├── story_state.py
│   ├── probability.py
│   ├── validator.py
│   └── simulator.py
│
├── ui/
│   └── pc_ui.py
│
├── audio/
│   ├── audio_player.py
│   └── ...
│
├── content/
│   ├── heroes.json
│   ├── locations.json
│   ├── items.json
│   ├── arcs/
│   └── scenes/
│
├── tests/
│
├── tools/
│   ├── simulate_stories.py
│   ├── validate_content.py
│   └── export_tts_manifest.py
│
├── config.json
└── README.md
```

Cette structure peut être améliorée si une organisation plus pertinente est proposée.

---

# 28. Tests

Créer des tests automatiques du moteur.

Tester notamment :

- les cinq héros ;
- les cinq lieux ;
- les cinq objets ;
- les 125 combinaisons initiales ;
- les probabilités ;
- les modificateurs ;
- les transitions ;
- les fins ;
- la durée estimée ;
- les sauvegardes debug ;
- la reproductibilité par seed.

Chaque combinaison initiale doit permettre de terminer au moins une aventure valide.

---

# 29. Contraintes d'écriture

Le contenu narratif doit éviter :

- répétitions excessives ;
- phrases génériques donnant une impression de texte généré automatiquement ;
- incohérences d'espace ou de temps ;
- apparition d'un personnage jamais présenté ;
- objet utilisé avant son acquisition ;
- informations que le joueur ne peut pas connaître ;
- changement inexpliqué de personnalité ;
- choix identiques formulés différemment.

Les scènes doivent être écrites comme un véritable conte oral.

Les transitions doivent être naturelles puisqu'elles seront ensuite lues à voix haute.

---

# 30. Fins multiples

Une aventure peut avoir différentes fins.

Ne pas réduire les conclusions à :

« victoire » ou « défaite ».

Prévoir notamment :

- grande réussite ;
- réussite difficile ;
- réussite obtenue grâce à un allié ;
- objectif principal atteint mais avec une conséquence ;
- secret découvert ;
- problème résolu d'une manière inattendue.

Même une aventure comportant beaucoup d'échecs doit arriver à une **vraie conclusion narrative satisfaisante**.

---

# 31. Ordre de développement demandé

Procéder dans cet ordre :

### Étape 1

Définir précisément le schéma JSON et l'architecture du moteur.

### Étape 2

Créer le moteur narratif générique.

### Étape 3

Créer la version PC et son mode debug.

### Étape 4

Créer plusieurs arcs et environ 120 minutes de contenu narratif.

### Étape 5

Créer les tests et simulateurs automatiques.

### Étape 6

Tester automatiquement les 125 configurations initiales et des milliers de parties.

### Étape 7

Corriger les incohérences, problèmes de durée et déséquilibres.

### Étape 8

Fournir une version PC directement testable ainsi qu'un README expliquant son lancement.

### Étape 9

Préparer l'abstraction nécessaire au futur portage Raspberry Pi Zero 2 W.

Ne pas commencer par optimiser pour le Raspberry Pi au détriment du prototype PC.

La validation du moteur et des histoires sur PC est prioritaire.

---

# 32. Résultat attendu de la première livraison

Je dois pouvoir lancer l'application sur mon PC, sélectionner par exemple :

```text
Héros :
Voleur / Voleuse au grand cœur

Lieu :
Cité flottante

Objet :
Grimoire vivant
```

puis jouer immédiatement une aventure complète d'environ 20 minutes.

À chaque étape, deux choix doivent m'être proposés.

Les probabilités et variables internes doivent être totalement invisibles en mode normal.

En recommençant avec les mêmes paramètres, l'aventure ne doit pas nécessairement être identique.

En changeant les paramètres initiaux, leur influence doit être perceptible dans l'histoire.

Enfin, le mode debug doit me permettre d'analyser précisément pourquoi chaque scène et chaque résultat ont été choisis.

Le principe directeur du projet est :

**donner l'impression d'un très grand nombre d'histoires uniques grâce à la combinaison intelligente de contenus écrits à l'avance, sans utiliser d'IA pendant la partie.**