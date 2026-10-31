# Lecteur autonome sur Raspberry Pi

Le Pi exécute le même service HTTP que le PC et répond à la même recherche
Wi-Fi de l’application Android. Les WAV sont copiés sur sa carte SD ; le PC
peut ensuite être éteint. La synthèse vocale et ses modèles restent sur le PC.

## Installation depuis le PC Windows

Prérequis : Raspberry Pi OS récent avec Python 3.10 ou plus, connexion SSH,
accès Internet pour les paquets Debian et une sortie audio USB branchée sur
le port USB de données du Pi. Le téléphone et le Pi partagent le réseau local.

Depuis la racine du projet sur le PC :

```powershell
python -m tools.serve_reader_install --host ADRESSE_DU_PC --target ADRESSE_DU_PI
```

Copier la commande Python affichée dans la session SSH du Pi. La lancer avec
le compte habituel, sans `sudo` devant `python3`. L’installateur demande lui-même
`sudo` si nécessaire pour installer `mpv`, `alsa-utils` et l’unité systemd.

Le transfert est limité à l’adresse du Pi indiquée et à une URL aléatoire.
Il s’arrête après une installation réussie ou après 30 minutes. Ctrl+C permet
de le fermer plus tôt. Il ne publie ni le dépôt entier ni un terminal distant.
Le pare-feu Windows doit permettre au Pi d’atteindre le port TCP 8766 du PC ;
l’outil ne modifie pas les règles du pare-feu.

Le paquet contient le moteur, les interfaces de télécommande, le catalogue et
les WAV existants des deux modes, avec leurs reçus adjacents. Les anciennes
prises des livres, références vocales, modèles TTS/ASR, caches de génération,
sauvegardes du PC et secrets sont exclus. L’APK Android est ajoutée si elle a
déjà été compilée. Aucune génération ou nouvelle vérification ASR n’est lancée.
Les empreintes SHA-256 du paquet et de chaque fichier sont contrôlées à la
réception. Les WAV et reçus sont conservés à l’identique.

Le paquet peut aussi être préparé sans démarrer de transfert :

```powershell
python -m tools.package_reader
```

Il est écrit dans `dist/raspberry/reader.zip`, ignoré par Git.

## Sortie USB et vérification

L’installation exige une unique carte USB avec sortie de lecture. Elle utilise
son identifiant ALSA stable, par exemple `alsa/plughw:CARD=Device,DEV=0`, plutôt
que son numéro de carte. Plusieurs cartes USB demandent une sélection explicite
avec `--audio-device` dans l’installateur.

Le diagnostic joue un WAV PCM silencieux de deux secondes sur la sortie réelle,
contrôle Pause/Reprise, volume, progression, rejeu et fin normale. Il ne joue pas
un conte et ne touche pas à la sauvegarde habituelle. Ce contrôle confirme la
lecture logicielle vers la carte ; une écoute d’un conte confirme ensuite que
l’enceinte est allumée et audible.

Linux utilise mpv avec ALSA, sans fenêtre graphique. Sa commande passe par une
socket privée héritée entre le service et son processus enfant. Seuls le
service HTTP (TCP 8765) et la découverte Android (UDP 18766) sont accessibles
sur le réseau. Le volume est celui du lecteur, sans modifier le mixeur général.
Une erreur de périphérique interrompt le passage ; elle ne compte pas comme
une fin normale permettant d’avancer automatiquement.

Pour lister les sorties sur le Pi :

```bash
aplay -l
mpv --no-config --audio-device=help
```

## Service et connexion Android

L’installation se trouve dans `~/.local/share/portes-imaginaire/`. Le lien
`current` désigne une version dans `releases/`. `sessions/` et `tmp/` sont
partagés entre versions. Une mise à jour garde les versions précédentes et
la sauvegarde du Pi ; elle n’importe pas la session de lecture du PC.

L’unité `portes-imaginaire.service` est activée au démarrage. Le lecteur tourne
avec le compte SSH habituel et l’accès au groupe audio, pas en root. Les droits
du service limitent les écritures à ses sauvegardes et à son cache de lecture.
Fermer SSH ne l’arrête pas.

Dans Android, toucher **Rechercher un lecteur sur le Wi-Fi**, choisir le nom du
Pi, puis saisir le code affiché à la fin de l’installation. Le lecteur demande
un nouveau code après chaque redémarrage du service. Le retrouver par SSH :

```bash
cat ~/.local/share/portes-imaginaire/sessions/remote/connection.json
```

Ce fichier privé contient le code courant, le port et le PID, jamais le jeton
du client. Le code n’est pas envoyé dans les réponses de découverte.

```bash
sudo systemctl status portes-imaginaire.service
sudo journalctl -u portes-imaginaire.service -n 40 --no-pager
sudo systemctl restart portes-imaginaire.service
sudo systemctl stop portes-imaginaire.service
```

Après un redémarrage, le passage est restauré sans émettre de son. **Lecture**
le relance au début. L’écoute automatique avance uniquement à la fin réelle du
WAV, respecte Pause et reste bloquée si un fichier est absent. Les deux modes
restent distincts et aucun WAV interactif ne remplace un WAV automatique absent.

Pour confirmer l’autonomie, fermer le lecteur PC, vérifier que le Pi apparaît
dans Android, lancer un conte, puis fermer SSH. Le contrôle du redémarrage
physique du Pi reste à faire lors de la première installation.

## Vérifications de développement

```powershell
$env:STORY_NATIVE_AUDIO = '1'
python -m unittest tests.test_pi_reader tests.test_reader_discovery tests.test_remote_control tests.test_pc_audio_tts
```

Les tests Pi couvrent l’IPC réelle avec un faux processus mpv, les erreurs
distinguées d’EOF, le choix ALSA stable, le confinement de l’unité, le contenu du
paquet et le rejet de fichiers corrompus ou de chemins sortant du répertoire.
Le diagnostic matériel s’exécute sur le Pi pendant l’installation.

Références : [IPC et sorties audio mpv](https://mpv.io/manual/stable/),
[audio Raspberry Pi OS](https://www.raspberrypi.com/documentation/computers/os.html#play-audio-and-video).
