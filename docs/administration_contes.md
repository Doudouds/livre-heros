# Administration des contes sur PC

Ouvrir **Administration des contes** à l'accueil, ou **Outils → Administration
des contes**. Le raccourci `Administrer_Contes.cmd` ouvre directement le panneau.

## Consulter les audios

Choisir un conte préparé puis **Jeu interactif** ou **Écoute automatique**.
Chaque ligne correspond à un fichier réellement joué : la première narration,
puis les variantes après le choix 1 ou le choix 2. Le Roi-grenouille comporte
21 fichiers interactifs et 11 automatiques.

Le panneau affiche **Prêt**, **À générer**, **En échec**, **À vérifier** ou
**En cours**. Un fichier est prêt lorsque son WAV et son reçu sont intègres,
que son texte et ses profils correspondent au conte actuel et que sa validation
finale par Whisper Medium est présente. Il ne suffit pas qu'un WAV existe.
Sélectionner une ligne pour lire son texte, ses personnages et les tons choisis.
**Écouter** lit le fichier avec sa seconde de silence déjà intégrée.

**Générer ce morceau** reprend la variante sélectionnée et les prises valides
de son cache. **Compléter les deux versions** traite d'abord le jeu, puis
l'écoute automatique, en conservant les fichiers déjà prêts. L'interface reste
utilisable pendant les calculs ; le journal et l'état des lignes sont actualisés.
L'écoute automatique suit le choix 1 et ne lit aucune annonce de choix.

## Demander une nouvelle prise

Sélectionner un audio prêt, puis **Refaire tout le segment**.
Le générateur utilise de nouvelles graines pour les portions de cette variante,
avec la même référence vocale, les mêmes textes et les mêmes profils approuvés.
Les autres variantes restent intactes.

La prise actuelle reste disponible jusqu'à la validation complète de sa
remplaçante. Un refus ou une interruption ne retire pas cet audio de la
bibliothèque.

### Refaire seulement une partie

Ouvrir **Portions à reprendre**. Chaque ligne est un passage déjà balisé avec
un ton : une phrase ou un groupe de phrases, un raccord, l'introduction ou
l'annonce des choix. Sélectionner une ligne pour lire son texte intégral et
**Écouter en service**. Avec Ctrl + clic, choisir plusieurs portions, puis
**Refaire la sélection**. Le texte reste identique.

Le menu **Ton de la reprise** contient tous les profils de la palette approuvée :
joie, tristesse, colère, peur, émerveillement, tendresse, surprise, détermination,
soulagement, soulagement apaisé, malice et neutre. **Conserver le ton actuel**
garde le rendu en service ; **Ton du manuscrit** rétablit le balisage initial.
Le choix s'applique uniquement aux portions sélectionnées au prochain lancement.
Il ne modifie ni la référence vocale, ni la palette globale, ni le texte du conte.
Les tons sont tracés dans le reçu et les recettes de la prise. Une reprise
ultérieure conserve ces tons ; restaurer une ancienne version rétablit aussi ses
tons. Le changement concerne cette variante et ce mode, pas les autres WAV.

Une portion en production apparaît en **rouge avec ⌛** ; les autres indiquent
qu'elles attendent, sont conservées ou passent les contrôles. En cas d'erreur,
le panneau affiche **⚠**, le motif du refus et le maintien de la version en
service. **Écouter le dernier essai** permet d'entendre la portion produite en
cache, même si l'assemblage complet n'a pas été publié. Ce bouton ne valide ni
ne publie cet essai. **Écouter en service** lit toujours la version publiée.
Les longs chemins de cache sont copiés dans un chemin de lecture court pour
le lecteur Windows ; leurs échantillons et leurs reçus restent intacts.

Seules les portions choisies reçoivent de nouvelles prises. Les autres sont
reprises depuis la version actuellement en service, avec exactement les mêmes
échantillons, même si cette version vient d'être restaurée. Le WAV entier est
réassemblé avec son silence initial et passe à nouveau le contrôle Medium.
Un composant manquant ou un refus concernant une portion hors sélection
arrête le remplacement : le logiciel ne refait pas silencieusement le reste.
Une interruption conserve la sélection et les portions nouvelles déjà terminées.

Quand seuls les choix ou une fin narrative sont mal reconnus, Medium contrôle
séparément les échantillons correspondants du WAV assemblé, avec les mêmes
critères. Une hallucination de reconnaissance sur la fin narrative ne doit
pas être attribuée aux choix ni provoquer leur régénération. Les transcriptions
brutes et les preuves de ces contre-vérifications restent auditées.

La sélection suit les limites du balisage vocal ; elle ne découpe pas un mot
ou une zone arbitraire au milieu d'une phrase.

### Comparer et restaurer les dix dernières prises

L'onglet **Historique · 10 prises** conserve jusqu'à **dix versions validées par
segment et par mode, version actuelle comprise**. Il indique la date, les
portions reprises et la version en service. **Écouter cette prise** permet la
comparaison. **Restaurer cette prise** contrôle à nouveau l'ancien WAV avec
Medium avant de le remettre en service, sans relancer Chatterbox. La version
remplacée reste dans l'historique ; un refus laisse le WAV courant intact.

Les WAV et leurs reçus sont conservés dans
`audio/experiments/IDENTIFIANT/cache/previous_versions/`. Après validation d'un
nouveau résultat, les versions les plus anciennes au-delà des dix sont retirées
de ce dossier. Les composants partagés du cache ne sont jamais supprimés. Les
anciens historiques sont reconnus. Les essais refusés par l'ASR ne sont pas des
versions livrables : leurs diagnostics et leurs prises de contrôle restent dans
le journal et le cache, sans occuper les dix places de versions validées.

Les contrôles ASR des portions, du fichier complet et de l'annonce titre/auteur,
les écritures atomiques et les 1 000 ms de silence sont conservés. L'interface
n'abaisse aucun seuil pour obtenir une prise.

**Arrêter la tâche** interrompt uniquement le processus lancé par le panneau
et ses enfants. **Reprendre** relance la dernière demande enregistrée. Son
identifiant stable évite de régénérer à nouveau un fichier déjà livré juste
avant une interruption. Les portions terminées sont réutilisées. Fermer le
panneau seul laisse la tâche continuer ; quitter l'application demande si
l'on souhaite l'interrompre. Les écoutes sont arrêtées au lancement d'une
génération pour libérer les WAV ; le passage du lecteur reste sélectionné.

Une action sur un seul morceau écrit son suivi dans le dossier de sa tâche,
sans remplacer le rapport du lot complet. La liste du panneau consulte les
fichiers effectivement disponibles et leurs reçus.

## Importer un conte avec Codex

1. Dans **Importer un conte**, renseigner **Titre du conte**, **Auteur(s)** et
   le **texte intégral**, collé ou chargé depuis un fichier UTF-8 `.txt`.
2. Cliquer sur **Préparer avec Codex**. Le texte est sauvegardé dans un brouillon
   local puis transmis à Codex avec les consignes de création du projet et la
   palette approuvée. La préparation utilise la connexion existante de Codex CLI.
3. Codex propose le découpage, deux choix à chaque arrêt, leurs raccords et les
   balises émotionnelles. L'application ajoute les identifiants, les transitions,
   les annonces de choix et l'introduction titre/auteur. Les deux chemins de
   chaque décision rejoignent la même scène suivante.
4. Relire l'onglet **Brouillon préparé · à relire**, puis cliquer sur
   **Intégrer le brouillon relu**. Une réponse invalide ou incomplète reste un
   brouillon ; elle n'entre pas dans la bibliothèque. La concaténation des
   corps des scènes doit reproduire tout le texte importé, espaces normalisés.
   Les tons inconnus, balises inexactes ou décisions sans deux choix sont refusés.
5. Dans l'onglet audio, lancer **Générer les premiers audios · 2 modes**. Écouter
   le premier fichier de chaque version, puis **Valider les premiers audios
   écoutés**. **Compléter les deux versions** devient alors disponible.

La préparation est une exécution Codex séparée, avec le contexte du projet ;
elle ne dépend pas de l'historique de ce chat. Elle utilise `codex exec` en
lecture seule, une réponse JSON structurée et l'entrée standard. Le modèle
utilise la configuration Codex habituelle : aucun modèle ni aucune clé API
n'est imposé par le panneau. Le bouton **Vérifier la connexion Codex** permet
de contrôler l'installation ; se connecter dans Codex ou avec `codex login`
si nécessaire. Une connexion Internet et un accès Codex actif sont nécessaires.
La [documentation officielle](https://learn.chatgpt.com/docs/non-interactive-mode)
décrit ce mode d'intégration et la réutilisation de l'authentification.

Pendant la préparation, Codex ne modifie pas le projet, ne publie rien et ne
génère pas d'audio. L'application valide la proposition avant l'intégration
explicite. Les brouillons, leurs sources, les résultats et les journaux sont
conservés dans `reports/admin/`, exclu de Git. L'intégration utilise un nouvel
identifiant et ne remplace aucun conte existant. Les fichiers d'un conte intégré
rejoignent `content/authored/books/`, `content/books/` et `config.json` ; aucune
publication Git n'est déclenchée par ces boutons.

La validation des premiers audios est liée au texte, aux WAV et aux empreintes
de la voix et de la palette. Une modification invalide cet accord. La référence
et les profils d'une série existante restent protégés contre le mélange.

## Commandes ciblées

Le panneau réutilise `generer_audio_conte.py` :

```powershell
python generer_audio_conte.py --book roi_grenouille --segment-id IDENTIFIANT_EXACT
python generer_audio_conte.py --book roi_grenouille --segment-id IDENTIFIANT_EXACT --regenerate
python generer_audio_conte.py --book roi_grenouille --segment-id IDENTIFIANT_EXACT --regenerate --span 2 --span 4
python generer_audio_conte.py --book roi_grenouille --segment-id IDENTIFIANT_EXACT --regenerate --span 2 --emotion joie
python generer_audio_conte.py --book roi_grenouille --segment-id IDENTIFIANT_EXACT --restore-take IDENTIFIANT_PRISE
```

Ajouter `--automatic` pour un identifiant de cette version. `--regenerate`
exige une sélection explicite ; `--regeneration-id` conserve la même demande
lorsque l'interface la reprend. `--dry-run` vérifie la sélection sans synthèse.
`--span` numérote les portions à partir de 1 et peut être répété. Il exige
`--regenerate`. `--restore-take` exige `--segment-id` et ne se combine pas avec
une nouvelle prise ni avec `--recheck-only`.
`--emotion PROFIL` exige une sélection `--span` ; `--emotion default` remet
le ton du manuscrit sur cette sélection. Les reprises de demandes interrompues
conservent le choix du ton.
