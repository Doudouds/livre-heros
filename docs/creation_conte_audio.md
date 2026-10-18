# Du texte source au conte audio

Ce guide conserve les décisions de travail prises avec l'utilisateur. Il sert
à préparer le prochain conte sans devoir retrouver cette conversation.

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
```

Le lanceur sélectionne automatiquement `.venv-tts\Scripts\python.exe` pour une
génération réelle, même si `python` désigne un autre environnement. Les chemins
par défaut sont calculés depuis le projet ; le lanceur fonctionne aussi depuis
un autre répertoire en indiquant son chemin absolu.

Options utiles : `--segment N --choice 2` pour un seul passage après les choix 2,
`--limit 2` pour les deux premiers fichiers du plan, `--attempts 3` pour les
essais, `--threads 8`, `--voice CHEMIN`, `--cache-dir CHEMIN`,
`--output-dir CHEMIN` et `--asr-model-dir CHEMIN`. Les profils émotionnels
proviennent toujours du balisage et de la palette.

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
3. Les réglages, poids V3 et versions sont identifiés. Chatterbox est chargé
   une seule fois, et les réglages changent entre les portions émotionnelles.
4. Chaque petite prise est contrôlée : format PCM, fichier complet et paroles
   reconnues par Whisper Small local, **sans le texte attendu comme prompt**.
   Les critères actuels sont un écart de mots au plus égal à 15 %, une fin
   retrouvée (trois derniers mots exacts et contrôle des huit derniers) et les
   annonces 1/2 présentes dans l'ordre, sans répétition.
5. Une prise refusée est conservée dans `rejected`, puis régénérée avec une
   autre graine, trois essais par défaut. Si nécessaire, le découpage est réduit
   avec une profondeur bornée. Les compteurs de graines sont persistants.
6. Le segment entier est retranscrit une nouvelle fois avec détection de parole
   pour éviter les hallucinations de sous-titres sur les silences. L'orthographe
   homophone « chois » est acceptée uniquement devant 1 ou 2 ; elle ne remplace
   jamais un numéro absent. Un refus intégral déclenche des prises dans un
   espace de cache distinct avec une nouvelle graine, sans toucher aux autres
   segments. Les essais intégraux sont également bornés.
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

## Vérifier une modification du pipeline

`tests/test_story_audio.py` couvre le balisage, les parcours, le cache, les
reprises, les refus et une mort brutale réelle d'un sous-processus. Exécuter
également les tests `test_roi_grenouille`, `test_speech_verification` et
`test_tts_batch`. Utiliser un dossier temporaire situé dans le projet si les
permissions du répertoire temporaire système empêchent les tests d'écrire.

Effectuer enfin un `--dry-run` exhaustif et une relance réelle du premier
segment déjà validé : sa conservation doit être confirmée sans charger le
modèle de synthèse. La préparation d'un lanceur ne justifie pas de générer
pendant les tests tous les audio que l'utilisateur lancera lui-même.
