# IPTV4FREE : icône distincte sur l'accueil Android TV

## Résultat attendu

Sur la télévision TCL, une nouvelle application Android nommée **IPTV4FREE**, avec le logo officiel, remplace le **raccourci** Kodi dans la rangée des favoris. Un appui sur IPTV4FREE lance le Kodi officiel, puis ouvre directement l'interface Kodi **script.iptv4free** déjà installée. Kodi, PVR IPTV Simple Client et MegaNexus sont conservés. L'application Android ne fournit aucune chaîne.

Ce projet se trouve dans `android-tv-launcher/` avec le package Android distinct `com.iptv4free.launcher`. Il ne modifie jamais l'APK de Kodi, ses icônes ni ses composants.

## Installation sur la TCL

1. Vérifier que Kodi et le module **IPTV4FREE 0.3.0** fonctionnent déjà sur la TV.
2. Dans Kodi, Paramètres > Services > Contrôle, activer le contrôle par des applications **sur ce système** (JSON-RPC TCP 9090). Ne pas activer le contrôle par d'autres appareils du réseau si ce n'est pas nécessaire.
3. Télécharger l'APK Android TV compilé : [IPTV4FREE-AndroidTV-Launcher-0.1.0.apk](https://github.com/searadacunha/IPTV4FREE/raw/refs/heads/feat/iptv4free-tv-ui/dist/IPTV4FREE-AndroidTV-Launcher-0.1.0.apk). Le lien n'est fonctionnel qu'après réussite de GitHub Actions et publication effective du fichier.
4. Installer cet APK sur la TV avec ADB autorisé, par exemple `adb install -r IPTV4FREE-AndroidTV-Launcher-0.1.0.apk`, ou avec un gestionnaire de fichiers Android TV.
5. Sur l'accueil TV, placer **IPTV4FREE** dans les applications favorites. Enlever **Kodi** de la rangée des favoris par appui long > Retirer des favoris, lorsque ton lanceur TCL propose cette option. **Ne pas désinstaller ni désactiver Kodi**, indispensable à la lecture. Kodi peut toujours rester visible dans Toutes les applications.
6. Appuyer sur la tuile IPTV4FREE avec la télécommande. Après le lancement de Kodi, l'interface IPTV4FREE doit s'ouvrir automatiquement.

## Fonctionnement

- L'activité Android dédiée possède `LEANBACK_LAUNCHER`, une icône 512 x 512 transparente et une bannière 320 x 180, issues proportionnellement du logo original du dépôt.
- Lors d'un appui sur la tuile, l'application récupère et lance l'intent officiel de `org.xbmc.kodi`, puis attend le serveur local `127.0.0.1:9090` (maximum 30 secondes).
- Après `JSONRPC.Ping`, elle vérifie le module `script.iptv4free` avec `Addons.GetAddonDetails` puis lance `Addons.ExecuteAddon`. Elle ne fait aucun appel réseau vers un serveur externe.
- Si Kodi n'est pas installé, si le module manque ou si le port 9090 n'est pas actif, l'application affiche un diagnostic et offre Réessayer / Ouvrir Kodi uniquement.
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

**Signature :** c'est un APK de test signé en mode DEBUG. Chaque runner GitHub peut utiliser une clé différente : lors d'une mise à jour ultérieure, `adb install -r` peut refuser une signature différente. Créer une clé de publication persistante et privée sur le Mac pour les versions stables. Ne jamais publier une clé privée dans GitHub. En cas de conflit de signature, ne désinstaller que `com.iptv4free.launcher`, jamais Kodi.

**Validation réelle :** la compilation GitHub ne garantit pas que la bascule directe fonctionne sur ta TCL. Faire une vérification physique quand aucune vidéo n'est en cours et vérifier le résultat en image / journaux Kodi. Sans essai ADB, présenter cette fonction comme non testée.

## Désinstallation

`adb uninstall com.iptv4free.launcher` ou Paramètres Android TV > Applications > IPTV4FREE > Désinstaller. Le module Kodi, toutes les chaînes, les favoris, le guide EPG et MegaNexus sont conservés.
