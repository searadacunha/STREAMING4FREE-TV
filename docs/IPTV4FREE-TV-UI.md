# IPTV4FREE — interface TV pour Kodi (prototype 0.1)

Interface originale plein écran 16:9, lisible à la télécommande, conçue pour les chaînes déjà présentes dans **Kodi PVR IPTV Simple Client**. Elle ne modifie **aucun** fichier ni composant de MegaNexus : elle s'ouvre comme un module indépendant nommé **IPTV4FREE**. Elle ne fournit aucune chaîne ni aucun flux.

Fonctions : chaînes en direct, groupes, programme en cours, recherche, favoris locaux, guide Kodi, démarrage d'une chaîne, retour vers Kodi, rechargement des chaînes. Affichage limité à 300 chaînes par groupe pour protéger la mémoire des TV modestes. Couleurs graphite et turquoise, illustrations originales.

## Installer sur la télévision

1. Vérifier que les chaînes sont déjà visibles dans Kodi / IPTV Simple Client (`iptv4free doctor` sur l'ordinateur).
2. Télécharger directement le [ZIP IPTV4FREE depuis GitHub](https://github.com/searadacunha/IPTV4FREE/raw/refs/heads/feat/iptv4free-tv-ui/dist/script.iptv4free-0.1.0.zip) ou, sur Mac/Linux, construire le même module à la racine du dépôt avec `python3 scripts/build_addon.py` (sortie : `dist/script.iptv4free-0.1.0.zip`).
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


## Logo officiel IPTV4FREE : installation et conservation

Le fichier PNG original envoyé dans la conversation est **blanc et bleu électrique**, avec le globe, l'orbite et les étoiles. Il doit rester identique, sans recoloration, redessin, génération IA ou déformation. Cet environnement n'a pas pu accéder aux octets binaires de la pièce jointe : le PNG **n'a pas encore été publié sur GitHub**.

**Une opération manuelle est nécessaire :** ouvrir la branche `feat/iptv4free-tv-ui`, puis le dossier `assets/branding/` sur GitHub, choisir **Add file → Upload files**, et déposer le PNG d'origine sous le nom exact `IPTV4FREE-original.png`. Ne pas mettre l'image dans `main` tant que la PR n'est pas validée.

Après cet upload, le workflow GitHub reconstruit automatiquement l'archive. Localement : `python3 -m pip install pillow`, puis `python3 scripts/build_addon.py`. Le script de packaging conserve une copie inchangée du PNG dans le dossier media de Kodi et produit un `icon.png` carré transparent de 512×512 par simple redimensionnement proportionnel et ajout de marges. `addon.xml` associe cette icône aux extensions Kodi. L'interface utilise l'image fournie comme en-tête, avec un titre texte de secours en l'absence du PNG.

Le ZIP `dist/script.iptv4free-0.1.0.zip` ne sera réellement **à jour avec le logo** qu'après la compilation réussie suivant l'upload. Ne pas confondre le fichier ZIP déjà publié auparavant et la nouvelle version marquée.
