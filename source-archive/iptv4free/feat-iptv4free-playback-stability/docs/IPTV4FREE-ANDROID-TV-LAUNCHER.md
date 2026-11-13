# IPTV4FREE : icône distincte sur l'accueil Android TV

## Résultat attendu

Sur la télévision TCL, une nouvelle application Android nommée **IPTV4FREE**, avec le logo officiel, remplace le **raccourci** Kodi dans la rangée des favoris. Un appui sur IPTV4FREE lance le Kodi officiel, puis ouvre directement l'interface Kodi **script.iptv4free** déjà installée. Kodi, PVR IPTV Simple Client et MegaNexus sont conservés. L'application Android ne fournit aucune chaîne.

Ce projet se trouve dans `android-tv-launcher/` avec le package Android distinct `com.iptv4free.launcher`. Il ne modifie jamais l'APK de Kodi, ses icônes ni ses composants.

## Installation sur la TCL

1. Vérifier que Kodi et le module **IPTV4FREE 0.3.1** fonctionnent déjà sur la TV.
2. Dans Kodi, Paramètres > Services > Contrôle, activer le contrôle par des applications **sur ce système** (JSON-RPC TCP 9090). Ne pas activer le contrôle par d'autres appareils du réseau si ce n'est pas nécessaire.
3. Télécharger l'APK Android TV compilé : [IPTV4FREE-AndroidTV-Launcher-0.1.2.apk](https://github.com/searadacunha/IPTV4FREE/raw/refs/heads/feat/iptv4free-tv-ui/dist/IPTV4FREE-AndroidTV-Launcher-0.1.2.apk). Le lien n'est fonctionnel qu'après réussite de GitHub Actions et publication effective du fichier.
4. Installer cet APK sur la TV avec ADB autorisé, par exemple `adb install -r IPTV4FREE-AndroidTV-Launcher-0.1.2.apk`, ou avec un gestionnaire de fichiers Android TV.
5. Sur l'accueil TV, placer **IPTV4FREE** dans les applications favorites et en retirer le raccourci **Kodi**. **Ne pas désinstaller ni désactiver Kodi**, indispensable à la lecture. Sur la TCL, l'accueil par défaut est **Projectivy Launcher** (vérifié le 08/11/2026) :
   - IPTV4FREE apparaît tout seul en tête de la rangée « Apps TV ». Pour fixer sa place : appui long sur OK sur la tuile, puis **Réorganiser** ;
   - pour retirer Kodi de cette rangée : appui long sur OK sur la tuile Kodi, puis **Masquer** (ou **Déplacer vers…** une autre catégorie). Le même menu contient **Désinstaller** : ne pas le choisir.
6. Appuyer sur la tuile IPTV4FREE avec la télécommande. Après le lancement de Kodi, l'interface IPTV4FREE doit s'ouvrir automatiquement.

## Fonctionnement

- L'activité Android dédiée possède `LEANBACK_LAUNCHER`, une icône 512 x 512 transparente et une bannière 320 x 180, issues proportionnellement du logo original du dépôt.
- Lors d'un appui sur la tuile, l'application récupère et lance l'intent officiel de `org.xbmc.kodi`, puis attend le serveur local `127.0.0.1:9090` (maximum 30 secondes).
- Après `JSONRPC.Ping`, elle vérifie que le module `script.iptv4free` est présent et **activé** (`Addons.GetAddonDetails`, propriété `enabled`), puis lance `Addons.ExecuteAddon` avec le paramètre `android`. Elle ne fait aucun appel réseau vers un serveur externe.
- Le module (0.3.1 ou plus) attend que le PVR de Kodi ait démarré avant de charger les chaînes. Lancé avec `android`, il réduit Kodi quand on le quitte (RETOUR depuis le menu, ou QUITTER) : on revient à l'accueil de la TV.
- Si Kodi n'est pas installé, si le module manque ou est désactivé, ou si le port 9090 n'est pas actif, l'application revient devant Kodi avec un diagnostic, Réessayer et Ouvrir Kodi uniquement. Un message Android (toast) double ce diagnostic, au cas où Android refuserait de ramener l'écran devant Kodi après les 30 s d'attente.
- Pas d'installation automatique sur la TV depuis GitHub, pas de modification des réglages Kodi, pas d'arrêt forcé de lecteur.

## Compilation

Exécuter depuis la racine du dépôt :

```sh
python3 -m pip install pillow
python3 scripts/prepare_android_launcher.py
cd android-tv-launcher
gradle :app:assembleDebug
```

Pré-requis : Java 17, Android SDK platform 35, build tools 35, Gradle 8.9. L'APK local est `android-tv-launcher/app/build/outputs/apk/debug/app-debug.apk`. La CI produit automatiquement un APK de test sous `dist/` sur la branche de la PR #3, avec validation de sa présence et du manifeste TV.

**Signature :** depuis 0.1.2, la CI signe l'APK avec une clé IPTV4FREE fixe, gardée dans deux secrets du dépôt (`IPTV4FREE_KEYSTORE_BASE64`, `IPTV4FREE_KEYSTORE_PASSWORD`) et en copie privée chez le mainteneur. Empreinte SHA-256 du certificat : `b44870f86baea816cc718b0efe1adf37bae4f7adf726d9ab09f613a9d30c6b78`. La CI refuse de publier un APK qui porte une autre empreinte. Les mises à jour s'installent donc par-dessus (`adb install -r`). Une seule exception : passer de 0.1.0 ou 0.1.1, signés par une clé de débogage différente à chaque compilation, à 0.1.2 oblige une dernière fois à désinstaller le lanceur. Un APK compilé ailleurs sans ces secrets reprend la clé de débogage de la machine. Ne jamais publier la clé privée. En cas de conflit de signature, ne désinstaller que `com.iptv4free.launcher`, jamais Kodi.

**Validation réelle (08/11/2026, TCL Android 12, Kodi 21.3, MegaNexus, 7 883 chaînes, APK 0.1.1 de la CI, module 0.3.1)** : tuile IPTV4FREE avec le logo dans Projectivy ; lancement à froid (écran IPTV4FREE puis liste) ; lancement avec Kodi déjà ouvert, module ouvert ou fermé (fenêtre du module en 1 s) ; RETOUR et QUITTER vers l'accueil de la TV, y compris pendant une lecture, qui s'arrête ; module désactivé (écran d'erreur devant Kodi, puis Réessayer une fois le module réactivé). Vérifications par captures d'écran, `dumpsys`, `kodi.log` et JSON-RPC.

Limites constatées :
- au démarrage à froid, l'accueil de Kodi (MegaNexus) reste visible environ 1,5 s avant IPTV4FREE (enregistrement d'écran). Le serveur JSON-RPC de Kodi ne démarre qu'après cet accueil, et la seule parade serait de modifier Kodi ou MegaNexus ;
- quand Kodi tourne en arrière-plan avec le module fermé, son accueil peut apparaître moins d'une seconde avant le module ;
- le cas « port 9090 fermé » (attente de 30 s) n'a pas été essayé : il aurait fallu changer un réglage de Kodi.

## Désinstallation

`adb uninstall com.iptv4free.launcher` ou Paramètres Android TV > Applications > IPTV4FREE > Désinstaller. Le module Kodi, toutes les chaînes, les favoris, le guide EPG et MegaNexus sont conservés.
