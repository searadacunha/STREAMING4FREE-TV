# IPTV4FREE — interface TV pour Kodi (prototype 0.1)

Interface originale plein écran 16:9, lisible à la télécommande, conçue pour les chaînes déjà présentes dans **Kodi PVR IPTV Simple Client**. Elle ne modifie **aucun** fichier ni composant de MegaNexus : elle s'ouvre comme un module indépendant nommé **IPTV4FREE**. Elle ne fournit aucune chaîne ni aucun flux.

Fonctions : chaînes en direct, groupes, programme en cours, recherche, favoris locaux, guide Kodi, démarrage d'une chaîne, retour vers Kodi, rechargement des chaînes. Affichage limité à 300 chaînes par groupe pour protéger la mémoire des TV modestes. Couleurs graphite et turquoise, illustrations originales.

## Installer sur la télévision

1. Vérifier que les chaînes sont déjà visibles dans Kodi / IPTV Simple Client (`iptv4free doctor` sur l'ordinateur).
2. Sur Mac ou Linux, à la racine du dépôt : `python3 scripts/build_addon.py`. Le zip est produit dans `dist/script.iptv4free-0.1.0.zip`.
3. Partager temporairement ce dossier sur le Wi-Fi local : `python3 -m http.server --directory dist 8765`. Dans Kodi, **Settings → File manager → Add source** puis URL `http://ADRESSE_IP_DU_MAC:8765`.
4. Dans Kodi : **Settings → System → Add-ons → Unknown sources**, activer pour cette installation si nécessaire, puis **Add-ons → Install from zip file → source IPTV4FREE → script.iptv4free-0.1.0.zip**.
5. Ouvrir **Kodi → Add-ons → Program add-ons → IPTV4FREE**. Le module est indépendant du thème installé. Certaines interfaces (dont MegaNexus selon la version) peuvent ne pas afficher les Program add-ons directement : dans ce cas, utiliser les menus Kodi natifs pour ouvrir le module; ne pas altérer MegaNexus.

Le bouton Retour quitte IPTV4FREE et retrouve Kodi et le thème précédemment utilisé. Pour supprimer l'interface : **My add-ons → Program add-ons → IPTV4FREE → Uninstall**. Les playlists IPTV Simple Client restent intactes.

## Inspecter la TV avec REA (facultatif)

Le dépôt officiel **REA** est https://github.com/morluto/rea. C'est un outil de diagnostic Android / rétro-ingénierie, **pas un thème Kodi**. D'après ses commandes de diagnostic ADB, après avoir autorisé l'accès ADB sur *ta propre TV* :

```sh
npx rea-agents setup
rea inspect-adb-client
rea list-adb-devices
rea inspect-adb-device SERIAL_TV
rea inspect-adb-display SERIAL_TV
rea inspect-adb-package SERIAL_TV org.xbmc.kodi
rea capture-adb-screen SERIAL_TV --output-directory ./rea-avant
```

Lire ensuite l'état ADB et tester l'interface, capture d'écran avant/après et retours télécommande. REA exige une connexion réelle autorisée; **aucun examen direct de la TV n'a été possible** pendant le développement de ce prototype. Ne pas extraire, adapter, recopier ni redistribuer le code ou les illustrations de MegaNexus, dont la licence est restrictive.

## Architecture

`kodi-addon/script.iptv4free/` : add-on Kodi `xbmc.python.script`, interface `WindowXMLDialog`, ressources PNG originales et commandes JSON-RPC locales (`PVR.GetChannelGroups`, `PVR.GetChannels`, `Player.Open`). Les favoris sont enregistrés dans le répertoire *profile* de ce seul add-on.

`scripts/build_addon.py` : empaquetage ZIP avec les deux textures graphiques.
`tests/test_tv_ui.py` : tests de la couche PVR sur des données entièrement synthétiques et contrôle de présence XML/assets.

**Limites :** prototype non validé en conditions réelles sur TV Android / Kodi 21-22, navigation et compatibilité MegaNexus à vérifier appareil allumé. Ce n'est pas un remplacement global de tous les écrans de Kodi.
