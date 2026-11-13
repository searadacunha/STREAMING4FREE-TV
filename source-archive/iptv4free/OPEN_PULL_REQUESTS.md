# Original open IPTV4FREE pull requests

Archived before deletion of the standalone repository. This preserves pull-request descriptions but not every inline review, workflow run or GitHub setting.

## #3 — IPTV4FREE 0.3.0 : interface TV Kodi avec le logo officiel

Original head: `feat/iptv4free-tv-ui` at `dad35d2d12fafda1875ff1afa931bc47f3813a85`.

## Objectif
Interface **IPTV4FREE** plein écran pour Kodi, avec le **logo officiel**, utilisable à la télécommande, sur les chaînes déjà configurées dans PVR IPTV Simple Client. Aucune modification de Kodi, d'IPTV Simple ni de MegaNexus ; aucun code ni image de MegaNexus.

![Accueil IPTV4FREE dans Kodi 21.3](https://github.com/searadacunha/IPTV4FREE/raw/refs/heads/feat/iptv4free-tv-ui/docs/images/iptv4free-kodi21-accueil.jpg)

*Capture de Kodi 21.3 sur Mac, playlist de test aux chaînes fictives.*

## ZIP installable (version 0.3.1)
[`dist/script.iptv4free-0.3.1.zip`](https://github.com/searadacunha/IPTV4FREE/raw/refs/heads/feat/iptv4free-tv-ui/dist/script.iptv4free-0.3.1.zip)
- 1 777 736 octets, SHA-256 `751c4d51441ecbee527f9c3044418b690b6a556f32c08cdefe091ac63fd5cf5f` ; le téléchargement GitHub donne le même SHA-256.
- Sur la TV, les 9 fichiers du module sont identiques à ce ZIP (SHA-256). Les 3 fichiers modifiés depuis 0.3.0 y ont été remplacés par ADB : « Installer d'un fichier Zip » n'a pas été refait pour 0.3.1.
- Reproductible : `python3 scripts/build_addon.py` donne le même fichier.
- Versions harmonisées : module Kodi 0.3.1, paquet Python 0.3.1, documentation 0.3.1 (0.3.0 n'est plus dans `dist/`).

## Changements
- **Logo officiel** `assets/branding/IPTV4FREE-original.png` (SHA-256 `895a691c…85bf`), copié tel quel dans le module ; `icon.png` 512 × 512 transparent déclaré dans `addon.xml`.
- **Interface** (`WindowXML` plein écran, bleu électrique / blanc / noir) :
  - groupes par pays et catégorie ;
  - programme en cours et suivant, programme complet de chaque chaîne ;
  - guide TV Kodi, favoris par nom, recherche ;
  - aperçu vidéo, retour depuis la vidéo ou le guide.
- **Corrections 0.3.0, vues sur la TV** :
  - **logos** : Kodi met l'image de l'émission dans `thumbnail` et le `tvg-logo` de la chaîne dans `icon`. Le module lit `icon` et affiche une image neutre si le logo manque ou ne répond pas (86 chaînes sans logo, plusieurs liens 404 à la source) ;
  - **compteur** « 300 / 7883 chaînes » tronqué par les polices plus larges de MegaNexus (+5 à +10 % mesurés) : il affiche maintenant « 300 sur 7883 » ;
  - **pagination** : la sélection revenait au rang 1 à l'arrivée de la page suivante (`addItems` reconstruit la liste) ; elle reste en place, et Bas sur la dernière ligne ne revient plus en haut ;
  - **focus** : retirer le dernier favori laissait la télécommande sans effet ; le focus revient sur FAVORIS ;
  - **vitesse** : chaque appel JSON-RPC coûte environ 0,35 s sur la TV, quelle que soit sa taille. Une page = un appel, l'index de recherche = un appel. Résultat : vue Favoris en 2,2 s au lieu de 26,5 s.
- **Installation par Wi-Fi** : `scripts/serve_addon.py`, qui répond aux plages d'octets. Avec `python3 -m http.server`, Kodi 21.3 plante pendant l'installation.
- README, `docs/IPTV4FREE-TV-UI.md`, CONTRIBUTING, SECURITY, notices tierces.

## Tests
- `pytest` : **86 réussis** (67 existants + 19 pour l'interface : données PVR, `default.py` contre de faux modules Kodi, logo, icône, XML, ZIP reproductible, serveur à plages).
- **Sur la TV**, le 08/11 : TCL, Android 12, 1,8 Go, Kodi 21.3, thème MegaNexus, 7 883 chaînes réelles. Fichiers installés identiques au ZIP (SHA-256).
  - Ouverture en 1,5 à 1,8 s, 32 à 72 ms par touche.
  - Changement de groupe, programme d'une chaîne en 0,3 s, pagination 300 → 600 sans perdre la sélection.
  - Favoris (ajout par MENU, vue, retrait), recherche « france 24 » (4 chaînes, 1,0 s).
  - Lecture (France 24, France 24 English, SIC Noticias), retour avec aperçu vidéo, changement de chaîne (part du module : 0,34 s), OK sur la chaîne en cours : plein écran en 0,17 s sans relancer le flux.
  - Guide TV avec retour.
  - Mémoire de Kodi : 240 Mo module fermé, 258 Mo ouvert.
  - Journal Kodi : aucune erreur Python.
- **Kodi 21.3 sur Mac** (07/11) : installation par le réseau, chaîne en panne, paramètres, état sans PVR, instance unique.

## Encore ouvert
- Le démarrage d'un flux dépend de sa source : de 1,6 s (SIC Noticias) à 18-30 s (France 24).
- Les logos officiels sombres (France 2 à 5) sont peu lisibles sur fond sombre.
- Les chaînes portugaises de la TV affichent des programmes français : correspondance du guide dans les playlists déployées, pas dans l'interface.
- Appui long sur OK de la télécommande TCL non essayé (touche MENU essayée).

PR en **draft** : ne pas fusionner dans `main` avant ta validation sur la TV.


## IPTV4FREE comme application Android TV (bouton sur l'accueil)

Le lanceur Android distinct `com.iptv4free.launcher` installe une tuile **IPTV4FREE** avec le logo officiel. Sur appui utilisateur il ouvre Kodi puis appelle `Addons.ExecuteAddon` pour `script.iptv4free` par JSON-RPC local TCP 9090. Kodi et MegaNexus restent installés et inchangés.

- **APK directement sur GitHub :** [IPTV4FREE-AndroidTV-Launcher-0.1.2.apk](https://github.com/searadacunha/IPTV4FREE/raw/refs/heads/feat/iptv4free-tv-ui/dist/IPTV4FREE-AndroidTV-Launcher-0.1.2.apk) (SHA-256 `f01d45225049575803e9c7274790c516c7d7643148d0f48fe895b432ef7da2c6`, compilé par la CI depuis 52c2e21 ; deux compilations indépendantes donnent le même fichier). Même code que 0.1.1, testé sur la TV ; seule la signature change.
- [Sources du lanceur](https://github.com/searadacunha/IPTV4FREE/tree/feat/iptv4free-tv-ui/android-tv-launcher)
- [Installation Android TV, contrôle Kodi et limites](https://github.com/searadacunha/IPTV4FREE/blob/feat/iptv4free-tv-ui/docs/IPTV4FREE-ANDROID-TV-LAUNCHER.md)

**Essayé sur la TCL le 08/11/2026** (accueil Projectivy, Kodi 21.3, MegaNexus, 7 883 chaînes). Anomalies trouvées avec l'APK 0.1.0 et le module 0.3.0, toutes corrigées puis revérifiées sur la TV :
- **démarrage à froid** : le module s'ouvrait avant la fin du démarrage du PVR de Kodi (`-32100`) et restait sur « Aucune chaîne », même en relançant la tuile. Le module 0.3.1 attend le PVR derrière « Chargement des chaînes… », puis affiche la liste en 12 à 15 s ;
- **RETOUR** : quitter le module menait à l'accueil MegaNexus. Lancé par la tuile (paramètre `android`), le module arrête la lecture et réduit Kodi : RETOUR et QUITTER ramènent à l'accueil de la TV. Ouvert depuis Kodi, il y revient comme avant ;
- **erreurs** : l'écran de diagnostic restait caché derrière Kodi. Il revient maintenant devant, avec un toast en secours. Un module désactivé affichait du JSON brut (`Invalid params`), remplacé par le message « pas installée ou activée ».

Vérifié aussi : la tuile et le logo, Kodi déjà ouvert (fenêtre en 1 s), la navigation, la sortie pendant une lecture de TF1, et Réessayer.

Limites :
- au démarrage à froid, l'accueil MegaNexus reste visible environ 1,5 s avant IPTV4FREE, car le JSON-RPC de Kodi démarre après lui ;
- le cas « port 9090 fermé » n'a pas été essayé ;
- **signature** : 0.1.0 et 0.1.1 étaient signés par une clé de débogage différente à chaque compilation, donc chaque mise à jour obligeait à désinstaller le lanceur. Depuis 0.1.2, la CI signe avec une clé IPTV4FREE fixe : deux secrets du dépôt, certificat SHA-256 `b44870f86baea816cc718b0efe1adf37bae4f7adf726d9ab09f613a9d30c6b78`. La publication est refusée si l'empreinte diffère. Passer de 0.1.1 à 0.1.2 demande une dernière désinstallation du lanceur, ensuite `adb install -r` suffit. 0.1.2 n'est pas encore installé sur la TV.

Ne pas désinstaller ni désactiver Kodi pour retirer son ancienne tuile : dans Projectivy, appui long sur Kodi, puis **Masquer**.



---

## #4 — Stabilité de lecture : relais HLS local, tests prolongés, diagnostic (module 0.4.0)

Original head: `feat/iptv4free-playback-stability` at `cf9a9dcae1ac42deb9cc6bb265d8151ecaf8ecf3`.

Branche empilée sur la PR #3 (`feat/iptv4free-tv-ui`) : le relais vit dans le module Kodi, qui n'existe que là. La PR #3 n'est pas modifiée.

## Diagnostic (mesuré le 08/11 sur la TCL et depuis le Mac)

- **Cause principale : le serveur source**, pas le Wi-Fi ni le décodage. Le relais qui porte TF1, France 2, TFX, 6ter et 7 autres chaînes françaises (`149.62.177.107:9999`, Flussonic) bride chaque connexion à ~3,9 Mb/s alors que le flux fait 4,8 Mb/s en moyenne (segments jusqu'à 8 Mb/s). `kodi.log` de la TV : **16 à 42 coupures / 10 min** sur 117 min, contre **0,4** pour Gulli (autre serveur), même TV, même soir. Wi-Fi de la TV −34 dBm / 650 Mb/s ; la TV télécharge sans pause (aucune demi-seconde inactive) ; ligne du Mac 352 Mb/s ; 2 connexions = 7,1 Mb/s.
- **Ouvertures de 16 à 23 s** sur Pluto TV / Samsung (`jmp2.uk`, 54 chaînes France) : Kodi 21 analyse toutes les variantes du maître avant d'en choisir une.
- Sans effet ici : cache Kodi 32/64 Mo (97 % des chaînes sont en HLS, lu par FFmpeg hors du cache Kodi), reconnexion FFmpeg d'IPTV Simple 21.11.0 (calculée mais jamais utilisée, `StreamUtils.cpp` l. 76 et 188), inputstream.adaptive (rend TF1 muet), bascule de source (TF1/TFX/6ter n'ont qu'une URL ; 72 chaînes sur 11 235 en ont plusieurs).

## Ce que fait la PR

- **Module 0.4.0 : relais HLS local** (`resources/lib/relay.py`, service Kodi `service.py`, `127.0.0.1:52180` seulement) : segments en 4 plages parallèles renvoyées dans l'ordre, maîtres réduits à la variante que Kodi choisit, aucun cache (URL signées et en-têtes conservés).
- `iptv4free health` : suit quelques flux comme un lecteur pendant des minutes (coupures, segments perdus, débit), puis à travers le relais quand c'est utile → `health.json`.
- Routage **mesuré** : seules les chaînes meilleures par le relais y passent (`build` avec `relay = true`, ou `tune` sur des playlists existantes, `tune --undo` pour revenir).
- Dédoublonnage : une source mesurée instable perd ; sinon la résolution décide (un FHD stable n'est jamais remplacé par un HD).
- `iptv4free playback-diagnose` : rapport en lecture seule, hôtes seulement.
- Doc : `docs/PLAYBACK-STABILITY.md`.

## Mesures (Kodi 21.3 du Mac, chaînes PVR IPTV Simple, 120 s)

| Chaîne | Direct | Relais |
|---|---|---|
| TFX | 64 s lues, 20 coupures | 117 s lues, 0 coupure |
| TF1 | 92 s lues, 11 coupures | 116 s lues, 0 coupure |
| MTV Classics (Pluto, 5 variantes, 40 s) | échec puis 20,2 s d'ouverture | 8,5 et 6,0 s |

Même résolution et même son dans les deux cas (1080p E-AC-3, 720p AAC).

## Tests

112 tests (`pytest -q`), dont 27 nouveaux : relais contre un faux serveur bridé par connexion (intégrité, débit, `Range: bytes=0-` de FFmpeg, plages fermées, erreurs, boucle locale), suivi HLS sur horloge simulée (y compris l'arrêt des téléchargements en fin de test), plafond de connexions par serveur, un seul flux par serveur dans `health`, classement des doublons, analyse de `kodi.log`, aller-retour `route`/`unroute`.

## Incident pendant les mesures (08/11)

`health` a d'abord suivi 3 chaînes du serveur de TF1 en même temps (12 à 15 connexions depuis la même adresse) : le serveur a refusé des connexions (19:37), puis répond **403 sur toutes ses chaînes à l'adresse de la maison depuis 19:57** (TF1, France 2, TFX, 6ter, LCI, TMC, France 5). Cause probable : un blocage anti-abus déclenché par ces mesures (non prouvé : pas d'autre adresse pour comparer). Corrections : `health` ne suit plus qu'un flux par serveur à la fois, le relais partage au plus 3 connexions parallèles par serveur. Avant de router ces chaînes sur la TV, il faut une lecture continue de 30 à 60 min par le relais sans blocage.

## Préparé, pas encore appliqué

- Playlists « tunées » (hors dépôt) : 7 chaînes France par le relais (France 2, France 4, France 5, TMC, 6ter, L'Équipe, RMC Découverte), 14 changements dans la base de Kodi, Portugal et Monde inchangés.
- **Rien n'est installé sur la TV** : elle a servi toute la soirée (TF1, YouTube, Gulli), puis s'est éteinte vers 20:00. Ordre prévu : module 0.4.0 par « Installer d'un fichier Zip », `deploy` des playlists (d'abord L'Équipe et RMC Découverte, puis les chaînes du serveur de TF1 quand il répond de nouveau et après l'essai long), lecture d'une chaîne routée, `playback-diagnose`.
- Mémoire et CPU du service sur la TV : non mesurés.

Ne pas fusionner avant l'essai sur la TV.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


---

