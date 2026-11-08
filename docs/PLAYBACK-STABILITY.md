# Stabilité de lecture (module 0.4.0)

Diagnostic et corrections du buffering sur la TCL Google TV (Android 12, 1,8 Go, Kodi 21.3,
IPTV Simple 21.11.0, 7 883 chaînes), mesurés le 08/11/2026.

## Ce qui coupe, mesuré

| Cause | Preuve | Part du problème |
|---|---|---|
| **Un serveur source bride chaque connexion** (~3,9 Mb/s) sous le débit du flux (4,8 Mb/s en moyenne, segments jusqu'à 8 Mb/s) | Mac : 1 connexion 3,9 Mb/s, 2 connexions 7,1 Mb/s, Cloudflare 352 Mb/s. TV : aucune demi-seconde sans téléchargement pendant TF1 (médiane 5,3 Mb/s, liaison Wi-Fi 650 Mb/s, −34 dBm) | 11 chaînes françaises (TF1, France 2, TFX, 6ter…) sur `149.62.177.107:9999` : **16 à 42 coupures / 10 min** sur 117 min dans `kodi.log`, contre **0,4** pour Gulli (autre serveur) le même soir |
| **Ouverture lente des maîtres à plusieurs variantes** | Kodi 21 lance `avformat_find_stream_info` sur toutes les variantes avant d'en choisir une (`DVDDemuxFFmpeg.cpp`, `HLSSelectProgram` après) | Pluto TV / Samsung TV Plus (`jmp2.uk`, 54 chaînes France) : 16 à 23 s |
| Puce Wi-Fi de la TV (blocages de 150 à 290 ms toutes les ~1,28 s, déjà documentés) | ping TV → 1.1.1.1 : moyenne 48 à 86 ms, gigue 67 à 106 ms | Ralentit un peu chaque connexion, **n'explique pas** les coupures : Gulli passe par le même Wi-Fi |
| Pas le décodage | `amc-h264(S)` (MediaCodec matériel, Surface), Kodi 48 % d'un CPU 4 cœurs pendant TF1 1080p25 | — |

Ce qui ne sert à rien ici :

- **Agrandir le cache de Kodi** (32 ou 64 Mo au lieu de 20) : 97 % des chaînes sont en HLS, lu par FFmpeg avec son propre HTTP ; `filecache.*` ne concerne que les ~220 flux HTTP directs. En direct, on ne met pas en réserve ce que le serveur n'a pas encore livré. Réglages laissés aux valeurs Kodi 21 (mode 4, 20 Mo, 4×, 128 Ko).
- **La reconnexion FFmpeg d'IPTV Simple** (`useFFmpegReconnect`, activée) : le code 21.11.0-Omega calcule l'URL avec les options (`StreamUtils.cpp`, lignes 76 et 188) mais ne l'utilise jamais.
- **inputstream.adaptive** sur ces chaînes : il rend TF1 muet (E-AC-3 annoncé comme AAC, constaté le 07/11) ; il reste coupé.
- **Basculer vers une autre source** : TF1, France 2, TFX et 6ter n'ont qu'une URL dans iptv-org ; 72 chaînes sur 11 235 ont plus d'une source vivante. Le choix de la source se fait donc à la construction (dédoublonnage mesuré), pas pendant la lecture.

## Corrections

1. **Relais local dans le module Kodi** (`resources/lib/relay.py`, service `service.py`) : écoute sur `127.0.0.1:52180` uniquement, démarre avec Kodi.
   - segments : 4 connexions en plages d'octets, renvoyés dans l'ordre au fur et à mesure (les requêtes `Range: bytes=0-` de FFmpeg aussi) ; plage fermée (`EXT-X-BYTERANGE`) et serveur sans plages : transmis tels quels ;
   - maîtres : seule la variante de plus haut débit (celle que Kodi choisit déjà) et ses pistes audio et sous-titres ;
   - aucun cache : chaque playlist est relue à la source, URL signées et en-têtes HTTP conservés (dans le jeton de l'URL locale) ;
   - erreurs de source dans `kodi.log` (« IPTV4FREE relay: », nom d'hôte seulement).
2. **Tests prolongés** : `iptv4free health` suit quelques flux comme un lecteur (playlist rechargée, segments entiers, tampon simulé), 2 à la fois, 120 s par défaut, puis refait le test **à travers le relais** quand il y a un problème ou plusieurs variantes. Résultats dans `health.json` (état local).
3. **Routage mesuré** : `relay_helps()` ne fait passer par le relais que les chaînes stables par lui et instables sans lui, ou à plusieurs variantes. `build` le fait si `[tv] relay = true` ; `tune` le fait sur des playlists existantes (`--undo` pour revenir aux sources).
4. **Dédoublonnage** : la source mesurée instable perd ; sinon la meilleure résolution gagne. Un FHD stable ou non mesuré n'est jamais remplacé par un HD.
5. **`iptv4free playback-diagnose`** : lecture seule. Kodi, module, relais, mémoire, CPU, Wi-Fi, pings, séances de `kodi.log` par serveur (ouverture, temps lu, coupures), causes avec un niveau de confiance. Hôtes seulement, rapport gardé sur le Mac.

## Mesures avant / après

Kodi 21.3 du Mac (même version que la TV), chaînes PVR IPTV Simple, son coupé, fenêtres de 120 s :

| Chaîne | Direct | Relais |
|---|---|---|
| TFX | 64 s lues, 20 coupures, ouverture 1,6 s | 117 s lues, 0 coupure, ouverture 1,8 s |
| TF1 | 92 s lues, 11 coupures, ouverture 3,0 s | 116 s lues, 0 coupure, ouverture 2,9 s |
| MTV Classics (Pluto, 5 variantes), fenêtre 40 s | échec, puis 20,2 s d'ouverture (17 s lues) | 8,5 et 6,0 s (30 et 33 s lues) |

Suivi type lecteur depuis le Mac (`health`, TFX, 150 s) : direct 15 coupures (47 % du temps), 9 segments perdus, 16/16 segments plus lents que le temps réel ; relais 0 coupure, 0 perdu, débit p10 9,0 Mb/s au lieu de 3,3. Qualité identique (1080p E-AC-3 pour TFX, 720p AAC pour MTV Classics).

## Utiliser

```bash
iptv4free --config TV.toml health --seconds 120          # favoris des playlists
iptv4free --config TV.toml health --duplicates          # sources concurrentes (après scan)
iptv4free --config TV.toml tune france.m3u --out tuned/ # ou : relay = true puis build
iptv4free --config TV.toml deploy                       # sauvegarde, contrôle, redémarrage si Kodi est libre
iptv4free --config TV.toml playback-diagnose
```

Le module 0.4.0 doit être installé sur la TV **avant** de déployer des chaînes routées.

## Revenir en arrière

- `iptv4free rollback` remet les playlists d'avant le déploiement ;
- ou `iptv4free tune <playlist> --undo --out <dossier>` puis `deploy` : chaque chaîne retrouve sa source, avec la même identité Kodi qu'avant ;
- module : réinstaller le ZIP 0.3.1 (le service disparaît avec lui).

## Limites

- Un serveur plus lent que le flux **même** avec 4 connexions, ou qui bride par adresse IP, reste coupé : `health` le dit (relais « unstable ») et rien n'est routé.
- Chaînes routées : si le module est désactivé, elles ne s'ouvrent plus (les autres ne dépendent pas du service).
- Les flux HTTP directs (MPEG-TS) et DASH ne sont pas suivis en profondeur (DASH : inputstream.adaptive a son propre tampon).
- Les mesures `health` se font depuis le Mac : même accès Internet que la TV, pas la même puce Wi-Fi.
