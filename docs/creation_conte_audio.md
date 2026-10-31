# Du texte source au conte audio

Ce guide conserve les décisions de travail prises avec l'utilisateur. Il sert
à préparer le prochain conte sans devoir retrouver cette conversation.

## Les deux versions sont obligatoires

Pour **chaque conte**, préparer le jeu interactif avec **les deux choix à chaque
étape**, et le conte en **écoute automatique**, du début à la fin sur le choix 1.
Le mode automatique ne lit ni question ni options. Les deux plans et les deux
lots doivent être vérifiés ; produire un seul mode ne constitue pas la livraison
complète. La validation initiale d'une nouvelle adaptation porte d'abord sur le
premier segment de chacun des deux modes, puis la production complète suit
après validation du rendu. Ne pas lancer toute la synthèse pour préparer un lanceur.

Les WAV finaux sont distincts, même lorsque les prises narratives sont partagées
dans le cache. Pour le Roi-grenouille : **21 WAV interactifs + 11 WAV automatiques
= 32 fichiers**, pour deux usages. Une génération des 21 variantes seule ne
crée pas les 11 WAV automatiques.

## Rédiger et intégrer le conte

1. Lire le texte source complet. Pour un PDF, extraire le texte et inspecter les
   pages rendues afin de corriger les césures, ligatures et sauts de lignes.
   Conserver le texte préparé et les pages d'origine dans les métadonnées.
2. Reprendre presque exactement le récit, dans son ordre, avec un narrateur à
   la **troisième personne**. Garder les dialogues et le dénouement. Ne pas
   remplacer le récit par un résumé ou une réécriture vague.
3. Ajouter deux choix à chaque arrêt naturel. Les choix changent un geste,
   une réaction ou une courte conséquence, puis rejoignent les événements du
   texte source. Les raccords restent distincts des paragraphes canoniques.
4. Garder héros, lieux et objets du texte quand leur personnalisation affaiblit
   le conte. Une adaptation fidèle peut s'ouvrir directement, sans le menu de
   personnalisation des aventures libres.
5. Créer `content/authored/books/IDENTIFIANT.json` et, pour une adaptation fidèle,
   `content/authored/books/IDENTIFIANT_source.txt`. Le Roi-grenouille fournit un
   exemple complet. Le format vocal actuel traite des textes explicites : pas
   de `values`, `variants`, `echoes` ni de conséquences conditionnelles implicites.
   Ces cas sont refusés avant génération plutôt que lus sans leurs annotations.
6. Ajouter le dossier de WAV à `config.json`, sous `book_audio_roots`. Définir
   `embedded_lead_in_ms: 1000` et `audio_lead_in_ms: 0` dans le conte.
   L'accueil PC affiche les nouveaux livres du dossier `content/books`.
7. Compiler, relire les choix et vérifier tous les chemins. La concaténation des
   corps des scènes doit reproduire le texte canonique préparé, espaces
   normalisés. La génération exporte les textes réellement obtenus avec
   `BookEngine`, raccord, question et annonces des deux choix compris.

## Annoter les émotions

### Annoncer le titre et l'auteur

Le premier segment de **chaque mode** commence par 1 000 ms de silence, puis
le titre complet et l'auteur, avant la première phrase du récit. Cette annonce
est lue une seule fois par écoute complète, jamais à chaque passage. Elle utilise
le profil neutre approuvé et reste hors des corps des scènes, afin de préserver
la fidélité au texte source. Le lecteur ne lit aucune balise technique.

Dans le manuscrit, renseigner par exemple :

```json
"audio_intro": {
  "author_credit": "des frères Jacob et Wilhelm Grimm",
  "text": "Le roi-grenouille ou Henri-le-Ferré, des frères Jacob et Wilhelm Grimm.",
  "audio_markup": "<voix emotion=\"neutral\" speaker=\"narrateur\">Le roi-grenouille ou Henri-le-Ferré, des frères Jacob et Wilhelm Grimm.</voix>",
  "pronunciations": [{"written": "Grimm", "spoken": "grime"}]
}
```

Le texte d'introduction est exactement `titre + ", " + author_credit + "."`.
Le champ `author` conserve les noms des auteurs. Les consignes de prononciation
s'appliquent aux mots entiers envoyés à Chatterbox : ici le mot français
« grime » sert à obtenir le son demandé « Grimme ». Le texte éditorial et l'ASR conservent
« Grimm » ; les seuils et vérifications ne changent pas. La recette identifie
la consigne et le code qui l'applique : un changement ne peut pas réutiliser
une prise de prononciation incompatible. Réutiliser cette annonce depuis le
cache dans les deux modes. Seuls les identifiants des premiers WAV changent ;
les segments suivants et les anciennes prises sont conservés.
L'annonce isolée est obligatoirement contrôlée par Medium, en plus du WAV
complet. Un nom mal reconnu ne peut donc pas être masqué par la longueur du
récit. Un refus de cette vérification reprend seulement l'annonce.

### Balisage des passages

La sélection de l'émotion est **éditoriale** : lire la scène et choisir le ton
approprié. Chatterbox reçoit du texte propre et des paramètres numériques.
Les balises sont interprétées par notre logiciel, et ne sont ni affichées dans
le jeu ni prononcées.

```xml
<voix emotion="neutral" speaker="narrateur">Elle regarda la fontaine.</voix>
<voix emotion="tristesse" speaker="narrateur">La jeune fille se mit à pleurer.</voix>
```

Le manuscrit conserve son `text` de référence et son `audio_markup`. Les deux
doivent contenir exactement les mêmes caractères après retrait des balises.
Le compilateur refuse toute différence. Il produit `audio_spans`, utilisé par
le générateur. Ce contrôle évite qu'une modification du balisage supprime un mot.

- Chaque scène possède `audio_markup` pour toute sa narration et ses dialogues.
- Chaque choix possède `consequence_audio_markup` pour le raccord lu au passage
  suivant. Les deux possibilités doivent être annotées.
- Chaque scène de décision possède `choice_audio_markup`, couvrant la question,
  « Choix 1 », son libellé, « Ou choix 2 » et son libellé. Ton neutre par défaut.
- Utiliser une émotion par phrase ou groupe de phrases cohérent. Garder les
  phrases assez longues pour une prosodie naturelle ; le découpage technique
  ultérieur limite les appels à 300 caractères.
- Les espaces et les paragraphes entre balises sont autorisés. Toute parole
  hors balise, émotion inconnue, balise imbriquée ou mal fermée est refusée.
  Écrire `&amp;` pour `&` et `&lt;` pour `<` dans le XML.
- `speaker` est un repère éditorial. Il ne sélectionne pas une autre voix : tous
  les personnages utilisent actuellement la même référence `Recording.wav`.

La palette validée est **la troisième série d'essais**, avec **malice A**.
Le fichier `audio/emotion_profiles.json` fait autorité : ne pas réinventer des
paramètres à chaque génération et conserver les anciens comparateurs HTML.

| Profil | Usage éditorial |
|---|---|
| `neutral` | Narration courante, transitions, annonces des choix |
| `joie` | Joie, enthousiasme, retrouvailles |
| `tristesse` | Chagrin, perte, déception |
| `colere` | Colère explicitement exprimée |
| `peur` | Crainte, inquiétude, menace ressentie |
| `emerveillement` | Beauté, découverte merveilleuse |
| `tendresse` | Douceur, réassurance, affection |
| `surprise` | Apparition inattendue, étonnement, incrédulité |
| `determination` | Fermeté, ordre, décision résolue |
| `soulagement` | Tension qui retombe, délivrance |
| `soulagement_apaisement` | Conclusion calme après le soulagement |
| `malice` | Sous-entendu, pensée rusée ou intention malicieuse |

Ces noms renvoient aux réglages validés, notamment `exaggeration` et
`cfg_weight`. Ils orientent le rendu ; la reconnaissance automatique ne mesure
pas l'émotion. L'écoute humaine du premier passage reste la validation du ton.

## Lancer la production hors conversation

Le [panneau administrateur PC](administration_contes.md), accessible depuis
l'accueil ou `Administrer_Contes.cmd`, fournit le suivi des deux modes, l'écoute,
la génération ciblée et les nouvelles prises avec conservation de la version
actuelle jusqu'à validation. Son formulaire d'import confie à Codex un brouillon
structuré en lecture seule, contrôlé puis intégré après relecture. Pour un
conte importé, valider les deux premiers audios avant de lancer les lots complets.
L'onglet **Portions à reprendre** refait uniquement les passages sélectionnés
en conservant les autres échantillons. L'historique garde dix versions validées
par segment et mode, actuelle comprise ; une restauration repasse le contrôle
intégral sans synthèse. Voir le guide du panneau pour ces actions et leur reprise.

Depuis PowerShell, dans le projet :

```powershell
python .\generer_audio_conte.py --dry-run
python .\generer_audio_conte.py --segment 1
python .\generer_audio_conte.py
```

Le lancement sans option produit tous les segments du **Roi-grenouille**, toutes
variantes de choix comprises. On peut aussi double-cliquer sur
`Generer_audio_Roi_Grenouille.cmd`. Pour un prochain conte préparé et configuré :

```powershell
python .\generer_audio_conte.py --book IDENTIFIANT --dry-run
python .\generer_audio_conte.py --book IDENTIFIANT --segment 1
python .\generer_audio_conte.py --book IDENTIFIANT
python .\generer_audio_conte.py --book IDENTIFIANT --automatic --dry-run
python .\generer_audio_conte.py --book IDENTIFIANT --automatic --segment 1
python .\generer_audio_conte.py --book IDENTIFIANT --automatic
```

### Écoute automatique, sans annonces de choix

À l'accueil du logiciel, cocher **Écoute automatique · sans choix** sur la
fiche du conte avant de l'ouvrir. Cette option est proposée pour les contes
balisés. Le lecteur suit le premier choix à chaque étape et conserve son
raccord narratif. Le texte et la voix ne présentent ni question au lecteur,
ni « Choix 1 », ni « Choix 2 ». Les boutons de décision et leurs raccourcis
clavier sont inactifs dans ce mode.

Préparer uniquement les audio de ce parcours avec :

```powershell
python .\generer_audio_conte.py --automatic --dry-run
python .\generer_audio_conte.py --automatic --segment 1
python .\generer_audio_conte.py --automatic
```

Ou double-cliquer sur **Generer_audio_Roi_Grenouille_Automatique.cmd**. Pour un
autre conte, ajouter `--book IDENTIFIANT`. `--choice 2` est refusé avec
`--automatic` afin de garder un seul parcours reproductible.

Ce mode prépare **11 fichiers** pour le Roi-grenouille, au lieu des 21 variantes
interactives. Les fichiers ont des identifiants au rôle `automatic` : le
lecteur ne risque pas de lire les annonces d'un ancien WAV interactif. Les
prises narratives et leurs émotions restent identiques et sont réutilisées
depuis le cache lorsqu'elles existent. Le contrôle intégral porte sur le texte
sans choix ; les vérifications, reprises et 1 000 ms de silence restent actives.

Le plan et l'état sont conservés dans `reports/IDENTIFIANT/automatic/`, pour ne
pas remplacer les rapports interactifs. Les WAV peuvent partager le même dossier
final grâce à leurs noms distincts. Le lecteur attend la fin réelle de chaque
WAV pour passer au suivant ; Pause suspend l'enchaînement. Rejouer relit le
passage courant, et Recommencer conserve le mode automatique.

Les fichiers de ce mode doivent être préparés avant de commencer une écoute
complète. Le logiciel vérifie leur présence et indique le lanceur à utiliser
s'ils manquent. Si un fichier devient indisponible pendant la lecture, elle
reste suspendue à ce passage ; Lecture permet de réessayer. Aucun WAV interactif
n'est utilisé en remplacement et aucun passage n'est sauté.

Pour ouvrir directement ce mode depuis la ligne de commande :

```powershell
.\Lancer.cmd --book roi_grenouille --automatic
```

Le raccourci `Ecouter_Roi_Grenouille_Automatique.cmd` ouvre directement ce mode
une fois les fichiers préparés.

Le lanceur sélectionne automatiquement `.venv-tts\Scripts\python.exe` pour une
génération réelle, même si `python` désigne un autre environnement. Les chemins
par défaut sont calculés depuis le projet ; le lanceur fonctionne aussi depuis
un autre répertoire en indiquant son chemin absolu.

Options utiles : `--segment N --choice 2` pour un seul passage après les choix 2,
`--limit 2` pour les deux premiers fichiers du plan, `--attempts 3` pour les
essais, `--threads 8`, `--voice CHEMIN`, `--cache-dir CHEMIN`,
`--output-dir CHEMIN` et `--asr-model-dir CHEMIN`. Les profils émotionnels
proviennent toujours du balisage et de la palette.

Après de nombreux refus, `--recheck-only` réécoute les fichiers et les prises
déjà en cache avec le contrôleur courant. Ce mode **interdit toute nouvelle
synthèse** : il peut récupérer une prise anciennement refusée, après une vraie
reconnaissance ASR réussie, mais laisse en échec les portions qui n'ont aucune
prise valide. Exemple :

```powershell
python .\generer_audio_conte.py --automatic --recheck-only
```

Le nouveau dossier `--output-dir` n'est pas automatiquement affecté au jeu :
mettre à jour `book_audio_roots` après validation si une autre série doit être
utilisée par l'application.

Pour le Roi-grenouille, **21 WAV** couvrent les **11 passages** : un premier
segment et deux versions de chacun des dix suivants. Les phrases communes
sont synthétisées une seule fois par profil et réutilisées depuis le cache.

## Contrôles et reprises

1. Le manuscrit est recompilé et toutes les paroles sont comparées au balisage.
   Le plan exhaustif est exporté avant une production réelle avec `--dry-run`.
2. Le WAV de référence est contrôlé, copié dans le cache sous son SHA-256 et
   figé pour la session. Un changement de référence, texte, modèle, environnement
   ou profil ne peut pas écraser silencieusement une série incompatible.
3. Les réglages, poids V3 et versions sont identifiés. Les paramètres de
   Chatterbox changent entre les portions émotionnelles. Pour limiter la RAM,
   les poids de Chatterbox sont libérés avant de charger le vérificateur Medium,
   et inversement. Un rechargement reprend les mêmes poids, référence,
   paramètres et graine ; il ne change pas le profil vocal.
4. Chaque petite prise est contrôlée : format PCM, fichier complet et paroles
   reconnues par Whisper Small local, **sans le texte attendu comme prompt**.
   Les critères actuels sont un écart de mots au plus égal à 15 %, une fin
   retrouvée (trois dernières unités normalisées exactes et contrôle des huit
   dernières) et les annonces 1/2 présentes dans l'ordre, sans répétition.
   La comparaison normalise une liste explicite d'homophones français, par
   exemple « délivré / délivrer », et certaines frontières de mots comme
   « ta balle / tabale ». Aucun suffixe n'est supprimé de façon générale.
   Le rapport conserve la transcription brute, son écart orthographique et
   l'écart après normalisation. Les fins absentes et annonces manquantes restent
   refusées ; les autres écarts restent soumis au même seuil de comparaison.
   Avant de refaire la voix, une reconnaissance non concluante est relancée
   une fois avec un autre décodage et détection de parole, sans prompt attendu.
   Si Small reste incertain, un **deuxième modèle, Whisper Medium**, vérifie le
   même enregistrement avec les mêmes critères. Les deux verdicts sont
   conservés. Le texte attendu ne sert jamais de prompt à l'un ou l'autre.
5. Une prise refusée est conservée dans `rejected`, puis régénérée avec une
   autre graine, trois essais par défaut. Si nécessaire, le découpage est réduit
   avec une profondeur bornée, uniquement aux fins de phrases ou de propositions.
   Les phrases complètes de secours contiennent au moins six mots, les
   propositions au moins huit (une citation complète peut en compter six).
   Aucune coupe artificielle après « de », « avec », un déterminant ou une
   autre amorce de groupe n'est admise. Ainsi « attelée de huit chevaux blancs »
   n'est plus coupé en « attelée de » puis un complément isolé.
   Les compteurs de graines sont persistants. Si le contrôleur a changé, les
   meilleurs anciens refus peuvent être réécoutés avant de demander une nouvelle
   prise. Les enregistrements d'origine sont conservés et la nouvelle preuve
   mentionne leur provenance et leur empreinte.
6. Le segment entier est obligatoirement validé par **Whisper Medium**, même
   lorsque Small avait accepté les portions. Un fichier final ne peut donc pas
   être approuvé par le seul petit modèle. Le seuil de 15 %, le contrôle de fin
   et les annonces requises restent identiques. Les horodatages de mots et la
   détection des hallucinations sur silence sont activés dans ce vérificateur ;
   aucune liste de phrases à supprimer n'est utilisée.
   Le segment entier est retranscrit une nouvelle fois avec détection de parole
   pour éviter les hallucinations de sous-titres sur les silences. L'orthographe
   homophone « chois » est acceptée uniquement devant 1 ou 2 ; elle ne remplace
   jamais un numéro absent. Si seul le dernier mot pose problème, la dernière
   portion est contre-vérifiée sur les échantillons prélevés à la fin du WAV
   réellement assemblé. Le rapport conserve les deux transcriptions.
   Si seuls les numéros ou le mot « choix » posent problème dans la transcription
   complète, Medium contrôle séparément la narration et la portion finale des
   annonces, prélevées dans ce même WAV. Les deux vérifications doivent passer
   intégralement, avec les annonces 1/2 exactes et dans l'ordre. Le reçu conserve
   le refus global, les deux preuves et les longueurs physiques ; l'audit
   recontrôle ces preuves. Un refus global déjà enregistré peut être réutilisé
   seulement si sa politique, son texte et les octets du WAV correspondent.
   Un refus persistant fait régénérer seulement les portions identifiées comme
   problématiques, avec une autre graine ; les autres sont conservées. Si le
   contrôle global reste incertain alors que chaque portion est validée,
   enregistrer ce doute et arrêter ce segment sans le régénérer entièrement.
   Les essais restent bornés et l'état conserve la graine de chaque portion.
7. Le segment reçoit **1 000 ms de vrai silence PCM au début**, puis il est
   publié par écriture atomique avec un reçu SHA-256. Les pauses entre portions
   valent 150 ms. Le lecteur n'ajoute pas les 800 ms des autres livres.
8. Le reçu est écrit après le WAV, avec un fichier de transaction `.pending.json`.
   Si le processus meurt entre ces deux écritures, la reprise reconnaît sa
   propre sortie et la reconstruit depuis les prises vérifiées. Un WAV présent
   sans preuve n'est pas considéré comme terminé.

**Ctrl+C**, fermeture de fenêtre, arrêt brutal de Python ou coupure de courant :
relancer la même commande. Il n'y a pas de `--resume` à ajouter. Les WAV validés
sont conservés, les prises réussies d'un passage incomplet sont réutilisées,
et une prise interrompue est refaite avec une nouvelle graine. Les fichiers
`.partial` ne sont jamais pris pour des résultats prêts. Les verrous système
empêchent deux productions simultanées dans le même dossier et sont libérés
par le système quand le processus meurt.

Les échecs ordinaires d'un segment sont enregistrés et le lot traite les autres
segments. Une erreur de modèle, un manque de mémoire ou une interruption arrête
le processus en conservant le travail. Le code de sortie est 0 si tout est prêt,
1 si un échec reste, 130 pour Ctrl+C. Une relance donne un nouvel ensemble
d'essais aux fichiers toujours refusés.

La vérification de voix repose sur l'empreinte de la référence et la traçabilité
de la génération ; elle ne constitue pas une reconnaissance biométrique du
locuteur. L'ASR vérifie le contenu, avec sa marge d'erreur, pas chaque phonème.

Les empreintes portent sur les octets des fichiers. Conserver les fins de ligne
LF des fichiers d'identité (`emotion_profiles.json`, `chatterbox_backend.py`,
`speech_verification.py`, `speech_review.py`, `pronunciation.py`) ; les règles sont inscrites dans `.gitattributes`.
Une conversion CRLF seule peut sinon rendre le cache incompatible alors que
les réglages n'ont pas changé. Ne pas supprimer les reçus ou désactiver leur
contrôle pour résoudre une différence d'empreinte.

## Fichiers conservés

- `reports/IDENTIFIANT/audio_plan.json` : plan complet, textes et émotions.
- `reports/IDENTIFIANT/generation_status.json` : état actualisé de chaque WAV.
- `audio/experiments/IDENTIFIANT/files` : WAV joués par le logiciel et reçus.
- `audio/experiments/IDENTIFIANT/cache` : prises, références figées, compteurs,
  recettes, contrôles, refus et journaux `story_events.jsonl`, `events.jsonl`,
  `chunk_events.jsonl`.

Ne pas supprimer ce cache pour reprendre. Si la référence originale a été
modifiée entre-temps et que l'on veut poursuivre la série précédente, fournir
sa copie figée avec `--voice CHEMIN_DU_CACHE\references\EMPREINTE.wav`.

Les dépendances ASR ont été conservées dans `audio/runtime/asr_dependencies`,
hors du dossier temporaire. Les chemins des poids locaux et la révision V3 sont
définis dans `audio/generation_settings.json`. Garder `.venv-tts`, ce dossier et
les caches de modèles pour fonctionner hors ligne. Sur un autre PC, recréer
l'environnement décrit dans `docs/chatterbox_v3.md` et installer les versions
ASR compatibles (faster-whisper 1.2.1, ctranslate2 4.8.3, onnxruntime 1.31.0,
av 18.1.0) dans le dossier ASR configuré, puis télécharger/copier les poids
locaux avant de lancer. Aucune clé d'API n'est nécessaire.

Le modèle d'arbitrage Medium est préparé une seule fois avec :

```powershell
.\.venv-tts\Scripts\python.exe -m tools.prepare_audio_review
```

Il provient du dépôt public `Systran/faster-whisper-medium` (environ 1,5 Go de
poids). Sa révision et ses empreintes sont conservées dans
`audio/runtime/asr_models/medium_revision.json`. Le téléchargement est
reprenable ; les lectures suivantes sont locales. `--offline` vérifie la
préparation sans télécharger. `asr_review_required: true` impose ce niveau de
contrôle : ne pas le désactiver pour faire passer un lot. Une absence de poids
arrête la génération plutôt que de revenir silencieusement à Small.

Lorsqu'on change de vérificateur, les WAV finaux intègres déjà produits sont
réécoutés directement. S'ils sont validés, seuls leurs reçus sont actualisés ;
leurs échantillons restent identiques. Pour le Roi-grenouille, la réparation a
abouti à **11 fichiers automatiques prêts, 0 échec**, avec les huit WAV d'origine
strictement conservés. L'audit reproductible `python -m tools.audit_automatic_audio`
vérifie les onze fichiers et enregistre ses résultats dans
`reports/roi_grenouille/automatic/quality_audit_medium.json`.

## Refus persistants sur un raccord ajouté

Lire la portion réellement bloquée et les transcriptions des deux modèles avant
de multiplier les relances. Un lot à 18/21 peut échouer seulement sur trois
phrases de raccord, alors que toute la narration commune est déjà en cache.

Une courte conséquence ajoutée pour un choix peut être reformulée pour une
lecture plus claire, à action et émotion identiques. Le corps canonique du
conte reste strictement inchangé. Par exemple, le raccord « il attendait
qu'elle tînt parole » peut devenir « il attendait qu'elle respecte sa promesse ».
Recompiler le manuscrit et son balisage, puis comparer les deux plans : seuls
les identifiants des variantes concernées doivent changer. Conserver les anciens
essais, les prises valides et les mêmes profils ; garder les contrôles ASR et
le seuil WER. Auditer les deux modes après la reprise.

## Vérifier une modification du pipeline

`tests/test_story_audio.py` couvre le balisage, les parcours, le cache, les
reprises, les refus et une mort brutale réelle d'un sous-processus. Exécuter
également les tests `test_roi_grenouille`, `test_speech_verification` et
`test_tts_batch`. `test_automatic_playback` contrôle le parcours du choix 1,
l'absence de questions, la fin réelle des WAV, Pause, les fichiers manquants
et la conservation du mode au redémarrage. Utiliser un dossier temporaire situé dans le projet si les
permissions du répertoire temporaire système empêchent les tests d'écrire.
`test_independent_review` vérifie notamment qu'un accord de Small ne peut pas
annuler un refus final de Medium, ainsi que la gestion mémoire et les frontières
naturelles du découpage de secours.
`test_audio_intro` contrôle l'annonce unique dans chaque mode, la conservation
des identifiants suivants, la prononciation tracée et les paroles canoniques
vérifiées par l'ASR, ainsi que la reprise de l'annonce depuis le cache.

Auditer les deux productions après génération :

```powershell
python -m tools.audit_automatic_audio --book IDENTIFIANT
python -m tools.audit_automatic_audio --book IDENTIFIANT --interactive
```

Pour une validation initiale seulement, ajouter `--segment 1` et, si nécessaire,
`--report-dir CHEMIN_DU_RAPPORT` pointant vers le dossier de son état de génération.

Effectuer enfin un `--dry-run` exhaustif et une relance réelle du premier
segment déjà validé : sa conservation doit être confirmée sans charger le
modèle de synthèse. La préparation d'un lanceur ne justifie pas de générer
pendant les tests tous les audio que l'utilisateur lancera lui-même.
