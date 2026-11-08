# IPTV4FREE : interface TV pour Kodi (module 0.3.1)

Interface plein écran 1920 × 1080 (16:9), pilotée à la télécommande, pour les chaînes déjà configurées dans **Kodi PVR IPTV Simple Client**. Elle porte le logo officiel IPTV4FREE et les couleurs bleu électrique, blanc et noir. Elle ne fournit aucune chaîne ni aucun flux, et ne modifie ni Kodi, ni IPTV Simple, ni MegaNexus.

![Accueil IPTV4FREE dans Kodi 21.3](images/iptv4free-kodi21-accueil.jpg)

*Capture réelle de Kodi 21.3 (Omega) sur Mac, avec une playlist de test aux chaînes fictives : la chaîne en cours de lecture apparaît en direct dans le panneau de droite.*

## Ce que fait l'interface

| Zone | Contenu |
|---|---|
| Colonne de gauche | Logo officiel, puis EN DIRECT, GUIDE TV, FAVORIS, RECHERCHE, GROUPES, PARAMÈTRES, QUITTER |
| Groupes | Les groupes réels d'IPTV Simple, affichés par pays et catégorie (`France · Info` devient FRANCE / Info) ; « Toutes les chaînes » en tête |
| Chaînes | Numéro, vrai logo de la chaîne (`tvg-logo`, lu dans le champ PVR `icon`), nom, programme en cours, barre de progression, repère FAVORI, repère blanc sur la chaîne en lecture. Sans logo, ou si son lien ne répond pas, une image neutre (contour de TV) |
| Panneau de droite | Aperçu vidéo de la chaîne en lecture (ou logo de la chaîne), programme en cours avec horaires et progression, programme suivant, programme complet de la chaîne |

**Télécommande**

| Touche | Effet |
|---|---|
| Flèches | Se déplacer ; ← et → passent d'une colonne à l'autre |
| OK sur une chaîne | Regarder (plein écran). OK sur la chaîne déjà en lecture : retour au plein écran, sans relancer le flux |
| → sur une chaîne | Programme complet de la chaîne ; OK sur une émission affiche son résumé |
| MENU ou appui long sur OK | Regarder, ajouter ou retirer des favoris, programme de la chaîne |
| RETOUR | Du programme vers les chaînes, des chaînes vers le menu, du menu vers Kodi |
| RETOUR pendant la vidéo | Revient dans IPTV4FREE, la chaîne continue dans l'aperçu |

GUIDE TV ouvre la grille complète de Kodi (tous les programmes, toutes les chaînes) ; RETOUR revient dans IPTV4FREE, sur le même bouton. PARAMÈTRES ouvre les réglages TV de Kodi.

**Pour une TV à 2 Go de RAM** : chaînes chargées par pages de 300 (la suite se charge trois rangs avant le bas de la liste, sans perdre la sélection), **une page = un seul appel JSON-RPC** (sur la TV, chaque appel coûte environ 0,35 s quelle que soit sa taille), programme complet chargé seulement à la demande, logos chargés en arrière-plan, recherche et favoris limités à 60 résultats. Mesuré sur la TV (08/11, 7 883 chaînes) : ouverture en 1,5 à 1,8 s, 32 à 72 ms par touche, Favoris en 2,2 s, recherche en 1,0 s ; Kodi passe de 240 Mo (module fermé) à 258 Mo (module ouvert, 600 chaînes chargées, index de recherche en mémoire).

**Favoris** : enregistrés par nom de chaîne dans `userdata/addon_data/script.iptv4free/favorites.json`. Ils survivent à une mise à jour des playlists, qui change les identifiants internes de Kodi (vérifié).

**Une seule copie** : si IPTV4FREE est resté ouvert derrière l'accueil de Kodi (touche HOME), le relancer ramène la fenêtre existante au lieu d'en ouvrir une deuxième.

## Installer sur la télévision

Prérequis : les chaînes sont déjà visibles dans Kodi (IPTV Simple Client). Sur l'ordinateur : `iptv4free doctor`.

1. Le ZIP est dans `dist/` du dépôt (branche `feat/iptv4free-tv-ui`), lien direct : [script.iptv4free-0.3.1.zip](https://github.com/searadacunha/IPTV4FREE/raw/refs/heads/feat/iptv4free-tv-ui/dist/script.iptv4free-0.3.1.zip). Depuis un clone, il est déjà en place ; un fichier téléchargé à part se range dans `dist/`. On peut aussi le reconstruire : `python3 scripts/build_addon.py` donne le même fichier, octet pour octet.
2. Le servir sur le Wi-Fi : `python3 scripts/serve_addon.py`. Le script affiche l'adresse à saisir dans Kodi, par exemple `http://192.168.1.30:8780/`.
   - **Ne pas utiliser `python3 -m http.server`** : Kodi lit les ZIP par plages d'octets (*ranges*), que ce serveur ignore. Kodi 21.3 n'arrive alors pas à lire le ZIP et **plante** pendant l'installation (constaté le 07/11/2026). `serve_addon.py` répond à ces plages.
3. Dans Kodi : **Paramètres → Gestionnaire de fichiers → Ajouter une source**, saisir l'adresse affichée, nommer la source `IPTV4FREE`.
4. **Paramètres → Système → Extensions → Sources inconnues** : activer, si ce n'est pas déjà fait.
5. **Extensions → Installer depuis un fichier ZIP → IPTV4FREE → script.iptv4free-0.3.1.zip**, puis arrêter `serve_addon.py` (Ctrl+C).
6. Ouvrir **Extensions → Extensions de programmes → IPTV4FREE**. Le module apparaît aussi dans les extensions vidéo.

**Désinstaller** : Extensions → Mes extensions → Extensions de programmes → IPTV4FREE → Désinstaller. Les playlists, IPTV Simple, MegaNexus et les réglages de Kodi ne sont pas touchés.

## Logo officiel

`assets/branding/IPTV4FREE-original.png` est le PNG fourni par Benjamin, conservé tel quel (1536 × 1024, RGBA, SHA-256 `895a691c86d56185416257ce026c540e49b49aaedf438c98c5242dcee60485bf`). `scripts/prepare_branding.py` en produit :

- `resources/skins/Default/media/iptv4free-logo.png` : copie octet pour octet, affichée dans la colonne de gauche et pendant le chargement ;
- `icon.png` : carré transparent 512 × 512 déclaré dans `addon.xml`. Seules les marges invisibles du PNG (alpha ≤ 1/255) sont retirées, puis le logo est réduit proportionnellement et centré, sans recoloration ni découpe de pixels visibles.

![Fiche de l'extension dans Kodi 21.3](images/iptv4free-kodi21-fiche.jpg)

Après remplacement du logo : `python3 -m pip install pillow`, `python3 scripts/prepare_branding.py`, puis `python3 scripts/build_addon.py`. Pillow ne sert qu'à la construction ; Kodi n'en a pas besoin.

## Thème Kodi complet (`skin.iptv4free`) : étude

Un thème Kodi remplace **toutes** les fenêtres de Kodi : accueil, réglages, lecteur et OSD, guide, enregistrements, clavier, dialogues. Estuary en compte plus de 150 fichiers XML, et une fenêtre absente du thème devient inutilisable. Les options :

- **partir d'Estuary** (GPL-2.0, Team Kodi) et le renommer : faisable, mais le thème passe sous GPL-2.0 et doit suivre chaque version de Kodi ;
- **sur la TV**, activer un thème remplace MegaNexus, qui est lui-même un thème (`skin.meganexus`) : l'accueil MegaNexus disparaîtrait. Les changements de thème ont déjà provoqué des gels au démarrage sur cette TV (journal du 06/11).

Décision pour 0.3.0 : rester un **module de programmes** autonome. Il fonctionne sous n'importe quel thème, ne touche ni à Kodi ni à MegaNexus, et s'affiche en plein écran avec sa propre identité. Un thème complet reste possible plus tard, sur une TV de test et avec l'accord de Benjamin.

Conséquence technique : Kodi n'utilise que les polices du thème actif. Le module emploie les noms de polices d'Estuary (`font12`, `font13`, `font30_title`…). Sous un autre thème, Kodi se rabat sur `font13` si un nom manque. Le rendu sous MegaNexus n'a pas été vérifié (sa licence interdit de lire son code).

## Inspecter la TV avec REA et ADB (facultatif, lecture seule)

[REA](https://github.com/morluto/rea) est un outil d'inspection Android et de rétro-ingénierie, pas un thème Kodi. Sur **votre** TV, avec ADB autorisé :

```sh
rea inspect-adb-client
rea list-adb-devices
rea inspect-adb-device SERIAL_TV
rea inspect-adb-display SERIAL_TV
rea inspect-adb-package SERIAL_TV org.xbmc.kodi
rea capture-adb-screen SERIAL_TV --output-directory ./captures-avant
```

`screencap` ne capture pas la couche vidéo de la TV : pour prouver qu'une chaîne joue, lire `Player.Time` par JSON-RPC ou le journal MediaCodec (`logcat`). Ne pas extraire, adapter ni redistribuer le code ou les images de MegaNexus.

## Architecture

- `kodi-addon/script.iptv4free/` : module `xbmc.python.script`.
  - `default.py` : fenêtre `WindowXML` plein écran. Comme c'est une vraie fenêtre Kodi, RETOUR depuis la vidéo ou le guide revient dedans.
  - `resources/lib/core.py` : appels JSON-RPC locaux (`PVR.GetChannelGroups`, `PVR.GetChannels`, `PVR.GetChannelDetails`, `PVR.GetBroadcasts`, `Player.Open`), sans dépendance à Kodi, donc testables.
  - `resources/skins/Default/1080i/IPTV4FREE.xml` : l'écran.
- `scripts/prepare_branding.py`, `scripts/build_addon.py` (ZIP reproductible), `scripts/serve_addon.py` (serveur Wi-Fi avec plages d'octets).
- `tests/test_tv_ui.py` : données PVR synthétiques, `default.py` exécuté contre des faux modules Kodi, logo, icône, XML, ZIP, serveur.

## Ce qui a été vérifié, et ce qui ne l'a pas été

**Sur la télévision** (TCL, Android 12, armeabi-v7a, 1,8 Go, Kodi 21.3, thème MegaNexus, 7 883 chaînes réelles), le 08/11/2026, avec le module 0.3.0 installé par « Installer d'un fichier Zip » (fichiers identiques au ZIP, contrôle SHA-256) :

- rendu sous MegaNexus : logo officiel, compteur « 300 sur 7883 » entier, vrais logos des chaînes, image neutre pour les logos absents ou cassés (RTP 1 et RTP 2) ;
- navigation à la télécommande (32 à 72 ms par touche), changement de groupe, programme complet d'une chaîne (0,3 s), dernière ligne d'un groupe sans retour en haut ;
- pagination au-delà de 300 : la page suivante arrive vers le rang 298, la sélection reste en place (600 sur 7883) ;
- favoris : ajout par MENU, vue Favoris, retrait, focus rendu au bouton FAVORIS quand la liste se vide ;
- recherche « france 24 » : 4 chaînes en 1,0 s ;
- lecture (France 24, France 24 English, SIC Noticias), RETOUR vers IPTV4FREE avec aperçu vidéo dans le panneau, passage d'une chaîne à l'autre (arrêt puis ouverture en 0,34 s), OK sur la chaîne déjà en lecture : plein écran en 0,17 s sans relancer le flux ;
- GUIDE TV (grille de Kodi) et retour sur le même bouton ;
- journal de Kodi : aucune erreur Python ; les seules erreurs viennent de logos de la playlist introuvables à leur source (404, nom de domaine inconnu).

Sur Mac (Kodi 21.3, 07/11) en plus : installation par le réseau, chaîne en panne (« Lecture impossible »), PARAMÈTRES, état sans PVR, une seule copie.

**Encore ouvert**
- Le démarrage d'un flux dépend de la source : 18 à 30 s pour France 24 (HLS), environ 1,6 s pour SIC Noticias. IPTV4FREE n'y prend que 0,3 s.
- Les logos sombres (France 2 à France 5) restent peu lisibles sur le fond sombre : ce sont les logos officiels tels qu'ils sont.
- Les chaînes portugaises de la TV affichent des programmes français (RTP 1 « Téléfoot ») : correspondance du guide dans les playlists déployées, pas dans l'interface.
- L'appui long sur OK de la télécommande TCL n'a pas été essayé (seule la touche MENU l'a été, par JSON-RPC) ; l'écran de chargement avec le logo est trop bref pour être capturé.
- Kodi réutilise un ZIP déjà lu sous le même nom : pour réinstaller la même version, servir le fichier sous un autre nom.
