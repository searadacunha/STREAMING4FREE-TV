# CLAUDE CODE — FINALISER IPTV4FREE AVEC LE LOGO OFFICIEL

**Mission** : terminer et livrer une interface Kodi/Android TV réellement utilisable appelée **IPTV4FREE**, en adoptant **exactement le logo fourni par l'utilisateur** (texte blanc métallisé « IPTV4 FREE », globe bleu électrique, anneau orbital et étoiles). Le visuel de référence a été transmis dans la conversation ChatGPT du 7 novembre 2026. Le logo est définitif : sa géométrie, ses inscriptions, ses effets, ses dégradés et ses couleurs ne doivent pas être modifiés.

Dépôt : https://github.com/searadacunha/STREAMING4FREE-TV
Branche existante : feat/iptv4free-tv-ui
PR existante : ../../
Source REA : https://github.com/morluto/rea

## 1. Première priorité : enregistrer le VRAI logo dans GitHub

Contrôle immédiatement le fichier \`assets/branding/IPTV4FREE-original.png\` sur la branche existante.

- Si présent : vérifie qu'il s'agit bien du PNG original de l'utilisateur, conserve-le intact, calcule son SHA-256 et renseigne ses dimensions, puis prépare les déclinaisons techniques.
- Si absent : cherche **uniquement** le fichier original dans les pièces jointes accessibles/locales (image déjà fournie par l'utilisateur) ou dans son téléchargement sur le Mac. Ne fabrique pas d'image approximative. Si le fichier n'est pas accessible, signale explicitement la seule action manuelle nécessaire : déposer le PNG par GitHub → branche \`feat/iptv4free-tv-ui\` → dossier \`assets/branding/\` → **Add file → Upload files** → nom \`IPTV4FREE-original.png\`. Continue le développement sans prétendre que le logo est intégré avant l'upload.
- Exécute \`python3 -m pip install pillow\` pour les outils de *build seulement* ; vérifie \`scripts/prepare_branding.py\`. Le script doit conserver l'image originale byte-for-byte pour l'affichage Kodi et produire une icône carrée transparente 512×512 par mise à l'échelle proportionnelle et marges. Zéro recoloration, nouvelle typographie, découpe des lettres ou déformation.
- Utilise l'image dans \`kodi-addon/script.iptv4free/resources/skins/Default/media/iptv4free-logo.png\`, et l'icône \`kodi-addon/script.iptv4free/icon.png\` dans \`addon.xml\` via \`<assets><icon>icon.png</icon></assets>\`. Vérifie le rendu dans l'interface et la fiche de l'extension Kodi.
- Conserve un titre texte de secours si le PNG n'a pas encore été uploadé, afin de ne pas casser le prototype. Ne prétends pas que ce module Kodi dispose d'une icône de *launcher Android* indépendante : cela demanderait une application/entrée Android TV distincte.
- Couleurs de l'application : bleu électrique/royal, blanc, noir et gris anthracite. Le turquoise de l'ancien prototype doit disparaître si non justifié. Le fond ne doit jamais compromettre la lisibilité du logo.

## 2. Audit du dépôt et architecture

Lis le README, \`docs/IPTV4FREE-TV-UI.md\`, le présent prompt, \`src/iptv4free/\`, le code du module Kodi, le workflow de création ZIP et la PR #3 avec ses résultats CI. Vérifie les APIs Kodi officielles avant de modifier les fichiers XML/Python. Garde toutes les fonctionnalités existantes : scan des M3U, filtrage, dédoublonnage, EPG/XMLTV, sauvegardes, déploiement ADB, \`doctor\`, rollback et intégration optionnelle MegaNexus.

MegaNexus a une licence restrictive : ne pas copier, modifier, traduire, réutiliser son code propriétaire ou ses graphismes, ni republier une version dérivée de MegaNexus. Réalise une interface **originale** par les APIs publiques Kodi/JSON-RPC et PVR IPTV Simple Client. Un skin original \`skin.iptv4free\` peut compléter le module si les vérifications le justifient, en respectant les licences d'éventuelles bases open source, mais ne dis pas qu'un simple Program Add-on remplace toute l'interface Kodi.

## 3. Résultat visuel et expérience TV

Créer une expérience native **1920×1080 16:9**, moderne, sombre et bleue, cohérente autour du **logo exact** :
- Accueil avec logo dans un en-tête lisible, navigation latérale réduite et sélection clairement visible.
- Sections : En direct, Guide TV, Favoris, Recherche, Groupes, Paramètres, Retour Kodi. Les groupes de pays doivent provenir de PVR, pas d'une liste fictive.
- Liste des chaînes avec numéro, nom, logo quand disponible, émission actuelle et suivante si disponible, heure de début/fin et progression si les données EPG le permettent.
- Navigation 100 % télécommande Android TV : flèches, OK, Retour, transitions de focus déterministes, état de chargement, absence de chaînes/EPG, utilisation sans souris.
- Lecture avec Kodi Player.Open, retour à la liste sans pertes de favoris ni blocage ; favoris et filtres robustes ; pas de relance/fermeture intempestive de Kodi.
- Optimiser pour une TV modeste (environ 2 Go de RAM), chargement progressif, pagination, textures réduites mais nettes, fluidité.

## 4. Inspection facultative mais utile avec REA

REA est un inspecteur d'APK/Android, pas un générateur d'interface. Si ADB et la TV sont joignables avec autorisation, commencer en lecture seule :
\`rea inspect-adb-client\`, \`rea list-adb-devices\`, \`rea inspect-adb-device SERIAL\`, \`rea inspect-adb-display SERIAL\`, \`rea inspect-adb-package SERIAL org.xbmc.kodi\`, \`rea capture-adb-screen SERIAL --output-directory ./captures-avant\`.

D'après ces résultats réels seulement, vérifier version Android/Kodi, résolution, architecture CPU, RAM, présence MegaNexus et PVR, navigation et rendu du nouveau logo. Sauvegarder la configuration Kodi avant installation. Ne rien écraser pendant la lecture. Si aucune TV n'est accessible, tester sur mocks ou émulateur et **indiquer clairement l'absence de validation réelle sur TV**.

## 5. Tests et publication GitHub

- Mettre à jour les tests Kodi/PVR/UI, avec données synthétiques, XML bien formés, chemins/focus cohérents, bitmap source et icon en 512×512, conservation du logo original, ZIP complet et enregistrement de l'icône dans \`addon.xml\`.
- \`python3 -m pip install -e ".[dev]"\`, \`python3 -m pip install pillow\`, \`pytest -q\`, \`python3 scripts/build_addon.py\`. Contrôler le ZIP généré et son contenu. Corriger les erreurs sans masquer les exceptions.
- Conserver la PR **#3** et la branche existante. Ne pas fusionner directement sur \`main\`, ne pas ouvrir de PR doublon, ne pas écraser d'éventuels commits concurrents. Publier le ZIP final dans \`dist/\` ou dans une Release vérifiée et donner le lien direct GitHub.
- Le ZIP précédemment publié sous le nom \`script.iptv4free-0.1.0.zip\` était un prototype **sans le logo fourni**. Ne le présenter comme « logo intégré » qu'après un nouveau build et contrôle du SHA, de la présence de \`icon.png\` et de la texture \`iptv4free-logo.png\` dans l'archive.
- Mettre à jour le README **sans en supprimer le style**, inclure une capture écran réelle seulement si elle existe, un lien de téléchargement ZIP GitHub, installation Kodi étape par étape et retour arrière.

## 6. Fin de mission : preuves exigées

Réponds avec : (1) lien GitHub du logo original et son SHA-256, (2) présence du logo dans la fiche d'extension Kodi et à l'écran, (3) lien direct vers ZIP final validé, (4) PR #3 et commits, (5) résultats exacts des tests, (6) compatibilité vérifiée ou non sur la TV, (7) instructions d'installation/désinstallation. Si le PNG d'origine n'est pas accessible, annonce précisément le blocage ; ne remplace pas le logo par une création IA et ne prétends jamais qu'un ZIP non marqué porte le logo.
