# Télécommande du lecteur PC depuis un téléphone

Cette première étape permet de contrôler les histoires depuis Safari, Chrome
ou un autre navigateur récent du téléphone. Le service Python et les WAV restent
sur le PC ; son périphérique audio habituel joue le son. Une connexion Internet
n’est pas nécessaire, mais les deux appareils doivent être sur le même réseau
local et pouvoir communiquer.

## Démarrage

1. Double-cliquer sur `Telecommande_Telephone.cmd`. Le lanceur ouvre aussi la
   télécommande dans le navigateur du PC pour faciliter les premiers essais.
2. Garder sa fenêtre de console ouverte. Elle affiche une ou plusieurs adresses
   « Téléphone », par exemple `http://192.168.1.20:8765/`.
3. Ouvrir cette adresse sur le téléphone. Le lien complet avec son fragment de
   connexion évite la saisie du code ; avec l’adresse courte, saisir les huit
   chiffres affichés dans la console. Les espaces sont facultatifs.
4. Choisir un livre et son mode, puis **Ouvrir cette histoire**. Le Roi-grenouille
   propose l’écoute automatique lorsque ses 11 fichiers sont présents. Le jeu
   utilise un plan distinct de 21 fichiers. **Actualiser les audio** recalcule
   leur disponibilité si une production vient de se terminer sur le PC.

Au premier lancement, Windows peut demander d’autoriser Python à communiquer.
Choisir le réseau privé utilisé à la maison. Le service ne modifie pas le
pare-feu automatiquement. Ne pas utiliser l’adresse `127.0.0.1` du PC sur le
téléphone : elle désigne l’appareil qui ouvre la page.

Le code change à chaque lancement. Après une connexion réussie, ce navigateur
retient le jeton pour retrouver la télécommande ; au prochain lancement du
service, il demandera le nouveau code. Aucun code ni jeton n’est enregistré dans
le dépôt ou dans la sauvegarde de lecture.

## Commandes et comportement

- **Lecture** reprend un son en pause à sa position ; après un arrêt, un fichier
  absent ou un redémarrage du service, elle relance le passage courant au début.
- **Pause** suspend le son et l’enchaînement automatique.
- **Rejouer** repart au début du passage courant. **Recommencer l’histoire**
  repart au premier passage, dans le même mode ; l’interface demande confirmation.
- **Arrêter** coupe le son et garde le passage pour une reprise ultérieure.
- Le **volume** est celui de cette lecture, indépendant du volume général de
  Windows. La barre montre la position réelle et la durée du WAV. Si le lecteur
  Windows de repli ne permet pas le volume, le réglage reste sur le PC.
- Le **jeu** affiche les deux choix et lit les WAV interactifs. Les anciennes
  aventures conservent leur introduction, leurs trois paramètres et leur bouton
  Poursuivre. Un passage sans audio reste accessible par son texte et ses choix.
- L’**écoute automatique** suit exclusivement le choix 1. Elle ne présente ni
  question ni options, utilise les WAV `automatic` et passe au segment suivant
  uniquement à la fin réelle du son. Un fichier manquant bloque ce passage ;
  Lecture permet de réessayer une fois le fichier rétabli. Aucun WAV interactif
  ou générique n’est utilisé en remplacement.
- Revenir à **Bibliothèque** ne coupe pas le son. Verrouiller le téléphone,
  fermer la page ou perdre son Wi-Fi laisse la lecture autonome continuer.
  La reconnexion récupère l’état réel du service.

Un seul lecteur et une seule histoire sont partagés par les téléphones connectés
à ce service. Des commandes simultanées sont traitées dans l’ordre. Un appui
ancien ou doublé est refusé si le passage ou l’état a changé, puis l’interface
actualise ses commandes. Une commande dont la connexion s’est interrompue n’est
jamais renvoyée automatiquement.

La progression et les choix sont sauvegardés par remplacement atomique dans
`sessions/remote/session.json`, ignoré par Git. Au redémarrage, le service restaure
le passage sans émettre de son ; appuyer sur Lecture pour l’écouter depuis son
début. Il ne restaure pas une position précise dans le WAV après un redémarrage.
Un contenu modifié ou une sauvegarde illisible sont signalés et n’empêchent pas
de commencer une nouvelle histoire.

Le titre et l’auteur restent dans le premier WAV préparé, avec son silence
initial. La télécommande ne les synthétise pas et n’ajoute aucun silence aux
contes configurés avec `audio_lead_in_ms: 0`. Les outils de génération, les
contrôles ASR, les reçus et les caches sont inchangés.

## Ligne de commande et dépannage

```powershell
python main_remote.py
python main_remote.py --open
python main_remote.py --port 8766
python main_remote.py --host 127.0.0.1
python main_remote.py --no-restore
```

`--host 127.0.0.1` limite les essais à ce PC. Par défaut, le service écoute le
réseau local sur le port 8765. `--no-restore` commence une nouvelle session tout
en conservant la sauvegarde automatique des prochaines actions. Ctrl+C dans la
console arrête le service et le son. Éviter de lancer plusieurs services à la
fois ou de faire jouer en parallèle l’application Tkinter.

Si le téléphone ne trouve pas le PC, vérifier le Wi-Fi, la console restée ouverte,
l’autorisation réseau privé de Python et l’adresse affichée au lancement. Les
réseaux « invités » isolent souvent les appareils. En présence de plusieurs
cartes réseau ou d’un VPN, choisir l’adresse du réseau partagé avec le téléphone.
Si le port est déjà occupé, fermer l’ancien lanceur ou choisir un autre port.
Après un changement de réseau du PC, relancer le service pour actualiser les
adresses et le code.

Cette version est une interface web locale : aucune installation depuis un
magasin d’applications n’est requise. L’installation complète comme PWA, le
déploiement sur Raspberry Pi et son éventuel point d’accès Wi-Fi restent les
étapes suivantes. La lecture sur Linux nécessite `aplay` ; le réglage du volume
et la progression de cette version ont été préparés pour Windows.

## Architecture et vérifications

- `main_remote.py` et `Telecommande_Telephone.cmd` : démarrage et adresses locales.
- `remote_control/controller.py` : orchestration indépendante de Tkinter,
  catalogue des WAV et sauvegarde. `PlaybackService` garde un seul fil pour les
  moteurs et les appels audio ; il avance même sans requête du téléphone.
- `remote_control/audio.py` : réutilisation du lecteur local, adaptateur MCI
  Windows avec volume par lecture et progression en millisecondes.
- `remote_control/server.py` : serveur HTTP et commandes JSON. Code de connexion
  temporaire, limitation des essais, jeton dans un en-tête, contrôle de l’hôte et
  de l’origine. Seuls les fichiers de l’interface sont publiés : ni WAV, ni
  répertoire du projet, ni sauvegardes. Les ressources sont locales, sans CDN.
- `remote_control/static/` : interface adaptée aux écrans de téléphone et PC.

```powershell
python -m unittest tests.test_remote_control tests.test_automatic_playback tests.test_pc_audio_tts -v
node --check remote_control/static/app.js
```

Pour inclure la vérification réelle du lecteur Windows avec un WAV silencieux :

```powershell
$env:STORY_NATIVE_AUDIO = '1'
python -m unittest tests.test_remote_control -v
```

Les tests couvrent les deux plans, Pause/Reprise, l’attente de la fin du son,
les fichiers supprimés pendant l’écoute, l’absence de repli interactif, les
choix doublés, les commandes concurrentes, la lecture sans client connecté,
la restauration de session et les accès réseau refusés. Les tests réseau,
MCI et Tkinter demandent une session Windows autorisant ces opérations.
