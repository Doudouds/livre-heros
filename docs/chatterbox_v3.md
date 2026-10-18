# Produire les voix avec Chatterbox Multilingual V3

Les textes sont déjà prêts. Le PC produit les voix une fois ; le jeu et le futur
Raspberry Pi lisent ensuite uniquement des WAV locaux. Chaque scène de décision
se termine dans **le même WAV** par :

> Que fais-tu ? Choix 1 : … Ou choix 2 : …

La conséquence de ton choix est un autre segment, puis la scène suivante contient
sa propre question et ses deux possibilités. Il n'y a pas de prompt séparé à
enchaîner à la main. Une partie complète comporte 26 segments : introduction,
12 scènes avec choix, 12 conséquences et conclusion.

## 1. Préparer ton échantillon

Créer `D:\livre_heros\audio\reference\ma_voix.wav` avec ta voix en français.
Pour le premier essai, je conseille 10 à 15 secondes de parole claire et continue,
sans musique, sans autre personne et avec peu d'écho. Lire un passage dans le ton
de narration souhaité. Garder ce même fichier pendant toute la production.

Le script utilise cet échantillon comme référence vocale ; il n'entraîne pas un
nouveau modèle. Il en conserve une copie identifiée par son empreinte dans le
cache local. Modifier la référence change le profil de production.

L'API officielle distingue **Multilingual V3** du modèle anglais et de Turbo.
Pour le français, notre adaptateur sélectionne explicitement `t3_model="v3"` et
`language_id="fr"`. V3 n'est pas le modèle sélectionné par défaut dans toutes les
versions du paquet. Voir la [documentation officielle de Resemble AI](https://github.com/resemble-ai/chatterbox#chatterbox-and-chatterbox-multilingual).

## 2. Installer l'environnement de production

Depuis PowerShell, dans `D:\livre_heros`, utiliser un environnement indépendant
du Python léger du jeu. Python 3.11 est la version testée par le projet officiel.
Cette commande suppose qu'il est installé et accessible par `py -3.11` :

```powershell
Set-Location D:\livre_heros
py -3.11 -m venv .venv-tts
.\.venv-tts\Scripts\python.exe -m pip install --upgrade pip
.\.venv-tts\Scripts\python.exe -m pip install "git+https://github.com/resemble-ai/chatterbox.git"
.\.venv-tts\Scripts\python.exe -m pip install faster-whisper
.\.venv-tts\Scripts\python.exe -m pip freeze | Out-File -Encoding utf8 reports\tts_environment.txt
```

L'installation depuis le dépôt officiel nécessite Git. Elle vise l'API récente
qui expose V3. Le paquet PyPI `chatterbox-tts` peut aussi convenir si sa version
expose bien cette sélection ; le script la contrôle avant de produire les voix.
Ne pas mettre à jour cet environnement au milieu d'un lot : sa version fait
partie du profil, et une mise à jour peut changer le résultat.

Pour vérifier si cet environnement voit une carte NVIDIA :

```powershell
.\.venv-tts\Scripts\python.exe -c "import torch; print('CUDA disponible :', torch.cuda.is_available())"
```

`--device auto` utilise CUDA si disponible, sinon le CPU. Le CPU peut prendre
beaucoup plus de temps ; le premier petit lot permet de mesurer ton PC. Si tu
dois installer une variante de PyTorch pour ta carte, partir des
[instructions officielles PyTorch](https://pytorch.org/get-started/locally/)
et respecter les versions demandées par le
[pyproject de Chatterbox](https://github.com/resemble-ai/chatterbox/blob/master/pyproject.toml).
La documentation Chatterbox indique des tests sous Debian ; l'installation et
la génération réelle sous Windows devront être validées sur ton matériel.

## 3. Exporter tous les textes et chiffrer le lot

```powershell
.\.venv-tts\Scripts\python.exe -m tools.export_tts_manifest --output reports\tts_manifest.jsonl
.\.venv-tts\Scripts\python.exe -m tools.generate_audio --dry-run
```

Le manifeste couvre les héros, lieux, objets, personnages rencontrés, révélations,
états du récit et conséquences possibles. Les substitutions sont déjà résolues.
Le `dry-run` donne le nombre de WAV, le nombre de passages réellement distincts,
la durée audio et une estimation du stockage PCM. Il fonctionne même avec le
Python du jeu, sans Chatterbox, sans voix de référence et sans téléchargement.

La durée audio globale peut être bien supérieure aux 120 minutes de texte
original : les variantes complètes reprennent plusieurs paragraphes communs.
Le cache évite de les synthétiser plusieurs fois, mais les WAV finaux doivent
contenir chacun leur scène complète. Prévoir la place annoncée avant de lancer
la production. L'estimation n'est pas une mesure du temps de calcul.

Pour le contenu livré, le plan donne 6 342 WAV, 1 299 passages distincts et
environ 22,4 Gio de WAV finaux, auxquels s'ajoutent le cache et les poids du modèle.

## 4. Faire un petit essai avec une décision complète

```powershell
.\.venv-tts\Scripts\python.exe -m tools.generate_audio --voice audio\reference\ma_voix.wav --device auto --scene lantern_1 --limit 6
```

Écouter les WAV créés dans `audio\files`. Vérifier la ressemblance avec ta voix,
le français, les noms propres, le débit et surtout la fin de la narration : les
deux choix doivent être lus intégralement. Lancer aussi `Lancer.cmd` pour vérifier
la lecture dans le jeu. Les fichiers absents laissent simplement le texte affiché.

Pour essayer d'autres réglages sans modifier ce premier lot :

```powershell
.\.venv-tts\Scripts\python.exe -m tools.generate_audio --voice audio\reference\ma_voix.wav --scene lantern_1 --limit 6 --cfg-weight 0.3 --output-dir audio\essai_lent
```

Les réglages par défaut sont `exaggeration=0.5`, `cfg_weight=0.5` et
`temperature=0.8`. Le champ `emotion` du manifeste est une annotation éditoriale ;
il n'est pas transformé en paramètre émotionnel inventé. La voix de référence et
ces réglages commandent la narration. Écouter avant de choisir les réglages du
lot complet. Le filigrane intégré par Chatterbox est conservé.

## 5. Générer tout, puis reprendre avec la même commande

```powershell
.\.venv-tts\Scripts\python.exe -m tools.generate_audio --voice audio\reference\ma_voix.wav --device auto
```

**Après une interruption ou un plantage, relancer exactement cette commande.**
Il n'y a pas d'option de reprise à ajouter.

- Chaque WAV terminé possède un reçu `.wav.json` avec son empreinte et le profil.
  Le reçu distingue l'intégrité du fichier et le contrôle des paroles.
  Un fichier vérifié est conservé ; un fichier tronqué est reconstruit.
- Les scènes longues sont découpées en passages de 380 caractères au maximum,
  sur les phrases et paragraphes. Chaque passage réussi est immédiatement sauvé.
  Si le script s'arrête au passage 4, les passages 1 à 3 restent utilisables.
- Les passages identiques sont partagés entre les scènes et les variantes.
  Leur graine dépend de leur texte et du profil, pas de l'ordre du traitement.
- Le WAV final est assemblé avec de petites pauses, puis remplacé atomiquement.
  Un reçu de transaction permet aussi de reprendre un arrêt entre le WAV et son reçu.
- Les erreurs isolées sont inscrites dans `audio\build_cache\events.jsonl`.
  Le lot continue avec les autres segments ; une nouvelle exécution retente ceux
  qui manquent. Une erreur de chargement du modèle ou de mémoire arrête le lot.
- Un verrou système empêche deux productions d'écrire simultanément les mêmes
  sorties. Il se libère lorsque le processus s'arrête, même après un plantage.

### Détecter une narration arrêtée trop tôt

Un WAV valide peut contenir seulement le début du texte. Le script contrôle donc
aussi les paroles avec [faster-whisper](https://github.com/SYSTRAN/faster-whisper),
un reconnaisseur exécuté localement sur le CPU. Chaque passage produit est
retranscrit en français, sans donner le texte attendu comme prompt au modèle.

La comparaison tolère de petites erreurs de reconnaissance, mais exige les
trois derniers mots du texte et contrôle les huit derniers mots. Pour les
questions, elle exige aussi les annonces « choix 1 » et « choix 2 » dans le bon
ordre. Un passage dont la fin manque est rejeté, même si sa durée et son format
WAV paraissent corrects.

Le script essaie trois prises avec des graines différentes. Si un long passage
reste suspect, il le découpe plus court et contrôle chaque morceau avant de
l'assembler. Ce découpage de secours est limité à deux niveaux. Une fin toujours
absente laisse le segment en échec ; elle n'est jamais acceptée par défaut.
Les prises rejetées et les transcriptions sont dans
`audio\build_cache\<profil>\rejected\<passage>`, pour permettre une écoute.
Un passage partagé qui échoue n'est pas retenté pour chacune de ses variantes
pendant le même lot. À la reprise, les tentatives utilisent de nouvelles graines.

Pour donner davantage d'essais aux passages restants :

```powershell
.\.venv-tts\Scripts\python.exe -m tools.generate_audio --voice audio\reference\ma_voix.wav --attempts 5
```

Le modèle de reconnaissance par défaut est `small`. Si les noms inventés sont
souvent mal reconnus, essayer `--asr-model medium`. Changer uniquement ce
contrôleur revalide les passages déjà produits sans refaire leur synthèse.
Si cette nouvelle vérification échoue ou est interrompue, l'audit cesse de
considérer les fichiers concernés comme prêts.
`--asr-model-dir` permet d'utiliser un modèle faster-whisper déjà préparé hors
ligne, avec `model.bin`, `config.json` et `tokenizer.json`. Le tokenizer local
est exigé pour éviter un téléchargement implicite. En mode normal, les poids
sont téléchargés une fois et leur révision est figée, comme ceux
de Chatterbox. Cette vérification ajoute du temps de calcul et du stockage.

La reconnaissance automatique peut se tromper, notamment sur les noms propres.
Elle ne constitue pas une garantie absolue de chaque mot prononcé. Une prise
correcte peut être refusée ; les diagnostics et l'écoute servent à trancher.
Une vérification finale à l'oreille reste nécessaire avant de considérer les
voix comme prêtes à être utilisées avec les enfants.

Le profil comprend la voix, les poids V3, les versions logicielles, le matériel
sélectionné et les réglages. Le premier lancement fixe une révision précise du
dépôt Hugging Face. Les reprises réutilisent cette révision et ses poids locaux.
Le premier téléchargement demande Internet ; aucune requête n'est nécessaire
pour jouer. `--model-dir` permet d'employer un dossier V3 déjà préparé hors ligne.

Une nouvelle voix, un nouveau modèle ou de nouveaux réglages déclenchent un
refus avant la modification des fichiers existants. Pour changer délibérément
la production, utiliser un autre `--output-dir`, ou `--overwrite` pour autoriser
le remplacement dans `audio\files`. Garder cette option dans la commande de
reprise du nouveau lot. Les anciens passages restent dans leur profil de cache.
Ne pas supprimer le cache ou les reçus pendant la production.

## 6. Vérifier et utiliser les fichiers

```powershell
.\.venv-tts\Scripts\python.exe -m tools.audit_audio --manifest reports\tts_manifest.jsonl
.\.venv-tts\Scripts\python.exe -m tools.verify_tts_coverage reports\tts_manifest.jsonl
```

Le premier contrôle vérifie les WAV présents, leurs reçus, les contrôles de
paroles réussis et les fichiers
manquants. Il mesure aussi la durée de parties complètes à partir des vrais WAV
si toute la couverture est disponible et signale les parcours hors de la cible
18–22 minutes. Le second vérifie la couverture des
textes dans le manifeste. Aucun de ces contrôles ne garantit à lui seul que le
TTS prononce correctement chaque mot : conserver une étape d'écoute.

Garder les WAV dans `audio\files` pour le PC. Pour le Pi, copier le contenu du
jeu et ce dossier ; le cache, l'échantillon de voix, les poids Chatterbox et
`.venv-tts` restent sur le PC. Les fichiers finaux sont mono PCM16, compatibles
avec le lecteur local. La durée vécue dépend du débit produit et du temps pris
pour répondre ; le chiffrage textuel à 150 mots/minute n'est qu'une estimation.

La reprise, la corruption de fichiers et les interruptions ont été testées avec
un synthétiseur de test. Les tests simulent aussi des fins manquantes, des choix
absents, des nouvelles prises et le découpage de secours. La ressemblance vocale
et le rendu Chatterbox réel ne
sont pas encore vérifiés : ils nécessitent ton échantillon et le petit lot.
