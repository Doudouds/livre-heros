# Application Android — Les Portes de l’Imaginaire

Cette application possède une interface Android native écrite en Kotlin. Elle
n’embarque ni navigateur ni WebView. Le téléphone sert de télécommande ; le
lecteur Python sur le PC garde les moteurs, la session et les WAV. L’application
continuera à utiliser la même API lorsque le lecteur sera porté sur Raspberry Pi.

## Installer et se connecter

1. Sur le PC, double-cliquer sur `Telecommande_Telephone.cmd`. Garder sa console
   ouverte et autoriser Python sur le réseau privé si Windows le demande.
2. Connecter le téléphone au même réseau local. Ouvrir le lien **Application
   Android** affiché dans la console, sous la forme
   `http://ADRESSE_DU_PC:8765/android`.
3. Télécharger l’APK puis l’ouvrir sur le téléphone. Android peut demander
   d’autoriser l’installation depuis le navigateur utilisé. Cette version de
   test est installée directement ; elle n’est pas publiée sur Google Play.
4. Ouvrir **Les Portes de l’Imaginaire**, puis **Rechercher un lecteur sur le
   Wi-Fi**. Toucher le PC ou le Raspberry Pi trouvé pour remplir son adresse,
   puis saisir les huit chiffres du code. Si un lecteur est déjà associé,
   passer par **Lecteur → Changer de lecteur** pour afficher cette recherche.
   La saisie manuelle d’une adresse comme `192.168.1.20:8765` et le collage du
   lien complet contenant `#connexion=…` restent possibles.
5. Dans la bibliothèque, choisir le livre et son mode. Pour un premier essai,
   sélectionner **Le roi-grenouille → Écoute automatique** lorsque son catalogue
   indique **11/11 fichiers prêts**.

L’APK peut aussi être copiée directement par USB depuis
`dist/android/LesPortesImaginaire.apk`. Le téléchargement local ne contient
aucun code de connexion et ne donne pas accès aux WAV, aux sauvegardes ou aux
autres fichiers du projet. L’adresse et le code restent nécessaires dans l’app.

Le bouton **Lecteur** permet de changer d’appareil sans arrêter l’histoire en
cours. L’adresse et le jeton sont conservés dans les préférences privées de
l’application, exclues des sauvegardes Android. Le code change à chaque
redémarrage du lecteur ; l’app demande alors le nouveau code. Aucun compte,
service cloud ou accès aux contacts n’est requis.

## Recherche sur le réseau local

Le lanceur PC active un petit répondeur UDP sur le port **18766**, en plus de
son serveur HTTP. Le téléphone effectue une recherche de trois secondes, avec
trois demandes espacées sur les adresses de diffusion de ses réseaux locaux.
Il utilise le Wi-Fi ou Ethernet lorsqu’ils sont disponibles, même sans accès
Internet. Les lecteurs répondent directement au téléphone avec leur nom et
leur port HTTP réel. Plusieurs lecteurs peuvent apparaître dans la liste.

Ce protocole ciblé ne parcourt pas les adresses IP et ne recherche pas d’autres
types d’appareils. Un identifiant aléatoire relie les réponses à la recherche
en cours ; les résultats sont dédoublonnés. L’adresse du lecteur est celle du
paquet reçu, et aucun code ni jeton n’est diffusé. La sélection d’un résultat
ne déclenche pas de connexion ou de lecture : le code d’association reste requis.

La recherche s’arrête à son échéance, lorsque l’application passe en arrière-plan
ou lorsqu’une connexion commence. Elle ne bloque pas les commandes du lecteur
et ne modifie pas le texte ou le code déjà saisis dans le formulaire.

Le PC doit utiliser le lanceur mis à jour et écouter le réseau local, comme le
fait `Telecommande_Telephone.cmd` par défaut. Un serveur limité à `127.0.0.1`
ou démarré avec `--no-discovery` reste accessible manuellement mais ne se
présente pas à la recherche. Si le port UDP est indisponible, le lecteur
continue de fonctionner et signale que la découverte n’est pas disponible.
Les Wi-Fi invités ou les règles bloquant les paquets UDP peuvent empêcher la
recherche ; l’adresse manuelle reste alors utilisable. Aucun réglage de
pare-feu n’est modifié automatiquement.

## Lecture

- **Bibliothèque** : livres et contes, choix du mode et disponibilité des WAV.
  **Actualiser les audio** recharge le catalogue après une génération sur le PC.
- **Lecture en cours** : Lecture/Reprise, Pause, Rejouer le passage, Arrêter,
  Recommencer l’histoire, volume et position réelle dans le WAV.
- **Jeu** : les deux choix sont affichés avant le texte facultatif du passage.
  Les aventures à personnaliser conservent le héros, le lieu, l’objet et leurs
  étapes Poursuivre. Les audio non préparés sont signalés ; le texte reste lisible.
- **Écoute automatique** : aucune question ou option, uniquement les WAV du
  parcours automatique. Le moteur du lecteur suit le premier choix. Un fichier
  manquant suspend l’écoute ; aucun WAV interactif n’est utilisé en remplacement.
- **Lire le passage** développe le texte sans modifier le son.

Verrouiller le téléphone, quitter l’application ou perdre son Wi-Fi n’envoie
aucune commande d’arrêt au lecteur. La lecture continue sur le PC. L’app recharge
l’état réel à son retour et désactive les commandes pendant une déconnexion.
Une commande n’est pas renvoyée automatiquement après une erreur réseau. Un
conflit de révision recharge l’état sans répéter un choix.

Cette version ne joue pas le son sur le téléphone et ne transfère pas encore
les contes vers le Raspberry Pi. Elle reprend les limites du contenu présent :
un livre dont les WAV ne sont pas tous préparés n’obtient pas de voix nouvelles.
L’interface web du lecteur reste disponible en parallèle.

## Compilation

Projet : `android/`. Ouvrir ce dossier dans Android Studio, ou exécuter depuis
la racine du dépôt **Compiler_Application_Android.cmd**. Ce lanceur utilise le
JDK d’Android Studio lorsqu’il est installé, puis le SDK indiqué par
`ANDROID_HOME` ou `%LOCALAPPDATA%\Android\Sdk`.

Versions épinglées : Android Gradle Plugin 8.12.2, Gradle 8.14.3 et Kotlin 2.2.20.
Le wrapper Gradle est livré avec l’empreinte SHA-256 officielle de sa distribution.
JDK 17 ou plus récent et SDK Android 36 sont nécessaires. Le premier lancement
peut télécharger des dépendances depuis Google et Maven Central.

```powershell
cd android
.\gradlew.bat --no-daemon testDebugUnitTest lintDebug assembleDebug
```

Le lanceur copie `android/app/build/outputs/apk/debug/app-debug.apk` vers
`dist/android/LesPortesImaginaire.apk` uniquement après réussite des contrôles.
L’APK est signée avec la clé de développement locale gérée par les outils
Android. Cette clé, `local.properties`, les caches, les sorties de compilation
et l’APK sont exclus de Git. Une publication en magasin demandera une signature
de distribution distincte ; aucune publication en magasin n’est faite ici.

L’application requiert **Android 8 / API 26** ou plus récent et cible l’API 36.
Ce niveau cible permet la connexion locale avec la permission normale
`INTERNET`, y compris sous Android 17 en mode de compatibilité. Un passage futur
à l’API cible 37 devra adopter la permission réseau locale ou le sélecteur
système prévu par Android.
[Documentation Android sur le réseau local](https://developer.android.com/privacy-and-security/local-network-permission).

La version 1.1 ajoute la permission normale `ACCESS_NETWORK_STATE` pour choisir
le réseau Wi-Fi/Ethernet de la recherche. Elle ne demande pas la localisation
et ne lit pas le nom du réseau Wi-Fi.

Le lecteur actuel utilise HTTP sur le réseau privé. Le client vérifie que les
adresses résolues appartiennent au réseau local, refuse les redirections et ne
désactive aucune vérification de certificat HTTPS. Il n’accède ni à un serveur
Internet public ni à une ressource arbitraire du lecteur. Les métadonnées et
commandes utilisent les mêmes routes authentifiées que la télécommande web.

## Vérifications

Les tests JVM couvrent les adresses, le filtrage du réseau local, l’association
par code, la lecture des deux catalogues audio, les deux choix, le mode
automatique, la progression, les fichiers absents, les révisions, les refus
d’authentification et les redirections. `lintDebug` vérifie la compatibilité des
API Android et des ressources. Le contrôle PC s’exécute séparément :

```powershell
python -m unittest tests.test_reader_discovery tests.test_remote_control -v
```

Pour les essais Android de ce projet, privilégier le téléphone connecté depuis
le projet Android Studio, conformément à la préférence de l’utilisateur. Le PC
et le téléphone partagent le même Wi-Fi ; la découverte utilise alors la
diffusion réelle du réseau. Pour les connexions manuelles, utiliser l’adresse
réseau du PC affichée dans sa console.

Le test d’intégration `ReaderDeviceTest` s’exécute directement sur Android avec
un lecteur de test contenant les 11 WAV automatiques du Roi-grenouille. Il
exerce le vrai client et `RemoteCoordinator`, sans simuler d’événements tactiles :
connexion, catalogue, lecture, pause, mise en arrière-plan, retour, reprise,
volume, rejouer, arrêt et recommencement. Il mémorise la connexion dans cet
appareil de test et laisse le premier passage en pause pour l’inspection.
Utiliser un lecteur de test distinct de la session habituelle.

Un second test contrôle la découverte UDP réelle. L’argument
`discoveryTarget=broadcast` utilise la recherche Wi-Fi normale du téléphone,
sans adresse de serveur fournie au client de découverte. Une adresse explicite
dans cet argument limite la recherche à une cible pour le diagnostic.

La version 1.1 a été compilée, contrôlée par lint et vérifiée par **14 tests JVM**
et **31 tests PC**. Les **deux tests d’intégration sur le Google Pixel 10a de
l’utilisateur, sous Android 17**, passent : découverte par diffusion sur son
Wi-Fi réel, connexion, catalogue, commandes audio et cycle de vie. Les tests
utilisent le projet Android Studio et ciblent explicitement ce téléphone.
La version installée est ensuite conservée avec la tâche `installDebug`.

Exemple de lancement depuis le projet Android Studio avec un téléphone connecté :

```powershell
$env:ANDROID_SERIAL = 'IDENTIFIANT_DU_TELEPHONE'
.\gradlew.bat --no-daemon connectedDebugAndroidTest '-Pandroid.testInstrumentationRunnerArguments.readerAddress=http://ADRESSE_DU_PC:PORT' '-Pandroid.testInstrumentationRunnerArguments.readerCode=CODE_A_HUIT_CHIFFRES' '-Pandroid.testInstrumentationRunnerArguments.discoveryTarget=broadcast'
.\gradlew.bat --no-daemon installDebug
```

La tâche de tests connectés peut désinstaller les APK à sa fin ; `installDebug`
remet l’application principale sur l’appareil. Le serveur utilisé pour ces
essais doit rester distinct de la session habituelle, car le test audio
commence et recommence le Roi-grenouille.
