# Contes interactifs et voix

Pour toute création ou adaptation de conte et toute préparation audio, lire
`docs/creation_conte_audio.md` avant de rédiger ou de générer. Ce document décrit
le parcours complet demandé par l'utilisateur : fidélité à la source, narration
à la troisième personne, choix, intégration, balises vocales, profils approuvés,
contrôle des paroles, reprise après interruption et livraison.

Les profils approuvés sont dans `audio/emotion_profiles.json`. La référence
vocale est `chatterbox/Recording.wav` : vérifier son contenu actuel par empreinte,
sans présumer qu'il est resté identique. Conserver les comparateurs d'émotions.

Pour les nouveaux contes balisés, utiliser `generer_audio_conte.py` et le pipeline
`tools/generate_story_audio.py`. Ne pas contourner les vérifications ASR, les
reçus, les écritures atomiques ou le cache pour gagner du temps. Chaque segment
livré contient 1 000 ms de silence initial ; le lecteur ajoute 0 ms pour ce conte.

Une adaptation nouvelle se valide d'abord sur le premier segment audio, sauf
instruction contraire de l'utilisateur. La création d'un lanceur complet ne
demande pas de lancer toute la synthèse pendant sa préparation. Vérifier le plan
complet avec `--dry-run` et la reprise avec les tests prévus dans le guide.

Le mode « Écoute automatique » suit toujours le choix 1, sans afficher ni
prononcer la question ou les options. Utiliser `--automatic` dans le générateur
et le même mode de `BookEngine` dans le lecteur. Les WAV portent le rôle
`automatic` ; ne jamais remplacer un fichier manquant par le WAV interactif.
La lecture avance à la fin réelle du son, respecte Pause et ne saute pas les
fichiers absents. Le Roi-grenouille nécessite 11 fichiers pour ce parcours,
contre 21 pour toutes les variantes interactives.

Après des refus ASR, distinguer une coupure réelle d'une orthographe homophone.
Les nouvelles règles de comparaison et la seconde reconnaissance sont dans
`audio/speech_verification.py`. Ne pas augmenter arbitrairement le seuil WER.
Utiliser `--recheck-only` pour réécouter et récupérer le cache sans synthèse.
Un doute sur la fin ne doit plus régénérer tout un segment : contre-vérifier
la fin du WAV assemblé, puis ne reprendre que les portions en cause.

Le contrôle final doit désormais être réalisé par le modèle indépendant
Whisper Medium (`asr_review_required: true`). Small reste le contrôle rapide
des portions ; ses refus sont arbitrés par Medium sans changer le seuil WER.
Ne pas ajouter des exceptions orthographiques pour forcer les trois passages
récalcitrants à passer. Utiliser le découpage de secours en phrases/propositions
complètes et préserver les huit WAV déjà validés lorsque leur réécoute réussit.
