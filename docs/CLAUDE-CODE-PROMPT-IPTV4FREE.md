# PROMPT CLAUDE CODE — IPTV4FREE / KODI / REA

Tu es ingénieur senior spécialisé en Kodi, Android TV, UI TV et intégration ADB. Tu disposes de l'accès local au projet, à GitHub et, si elle est connectée et autorisée, à ma télévision Android. Agis, implémente, teste et publie : je veux un résultat utilisable, pas une simple proposition.

## Références à étudier obligatoirement

1. Mon dépôt : https://github.com/searadacunha/IPTV4FREE
2. Ma PR existante : https://github.com/searadacunha/IPTV4FREE/pull/3
3. Branche de travail : `feat/iptv4free-tv-ui`
4. REA : https://github.com/morluto/rea (outil d'analyse Android, pas une interface graphique).
5. Kodi : architecture officielle skins/add-ons, interfaces JSON-RPC et PVR IPTV Simple Client.
6. MegaNexus est installé chez moi par-dessus Kodi : documente sa présence et sa compatibilité sans copier, extraire, adapter ou redistribuer son code, sa marque ou ses illustrations. Sa licence est restrictive.

Lis tous les fichiers utiles : README, `src/iptv4free/{kodi,meganexus,cli,adb}.py`, `kodi-addon/script.iptv4free/`, `docs/IPTV4FREE-TV-UI.md`, le workflow `.github/workflows/kodi-ui.yml`, les tests et la configuration. Lis les commits/retours CI de la PR #3 avant de modifier quoi que ce soit. **Ne réécris pas le README de zéro.**

## Objectif produit — IPTV4FREE

Je veux une véritable expérience de télévision, visuellement soignée et unifiée, appelée **IPTV4FREE**, qui repose sur Kodi pour la lecture et sur les chaînes déjà gérées par mon pipeline M3U/EPG. Le prototype actuel est un add-on de programmes : considère-le comme une base de travail, pas comme le résultat final.

Crée une interface **16:9 1920×1080**, sobre, moderne, rapide, avec :
- identité IPTV4FREE unique, fond graphite presque noir, accents turquoise subtils, typographie lisible depuis un canapé, textures originales et légères ;
- accueil immersif, raccourci « En direct », groupes Portugal / France / Monde lorsque ces données existent réellement, favoris, recherche, guide TV, paramètres et retour ;
- rail de chaînes avec noms, numéros, logos disponibles, programme actuel et si possible suivant, progression de programme et état du direct ;
- télécommande Android TV entièrement fonctionnelle : directions, OK, Retour, pression longue si utile, focus toujours visible et prévisible, aucun blocage de navigation ;
- lancement de la chaîne sélectionnée, retour depuis la vidéo, conservation des favoris et des numéros, navigation stable même si la liste se rafraîchit ;
- écrans d'erreur/chargement/absence d'EPG présentables et non bloquants, sans données fictives.

Choisis l'architecture réelle la plus robuste : amélioration du `script.iptv4free` autonome, puis **skin Kodi original `skin.iptv4free`** si les APIs et le temps de validation le permettent. Une véritable personnalisation de l'écran d'accueil est prioritaire ; n'annonce pas qu'un simple module de programmes remplace tous les écrans Kodi. Si un raccourci Android TV distinct est faisable sans fragiliser Kodi, ajoute-le séparément, mais ne modifie pas l'APK officiel de Kodi.

## Inspection REA et sécurité

Sur mon Mac, trouve le checkout local et la configuration réelle de l'application. Utilise REA uniquement si disponible/utile, en commençant par les commandes de découverte `rea inspect-adb-client`, `rea list-adb-devices`, `rea inspect-adb-device SERIAL`, `rea inspect-adb-display SERIAL`, `rea inspect-adb-package SERIAL org.xbmc.kodi` et `rea capture-adb-screen`, conformément à la documentation officielle. N'invente pas un état de TV, un serial, une IP ni une capture.

Si ma télévision est joignable avec ADB autorisé : fais une inspection en lecture seule, sauvegarde les paramètres et écrans avant toute installation, identifie la version de Kodi, la résolution, la RAM, les add-ons en place et l'état de PVR. Ne stoppe ni ne désinstalle Kodi pendant une lecture ; n'écrase pas MegaNexus et ne touche pas aux comptes ou médias. Si l'accès ADB est absent, poursuis l'implémentation et les tests hors ligne sans déclarer avoir validé la TV.

## Contraintes techniques

- Réutiliser les playlists, groupes, IDs, EPG et favoris de l'architecture existante dans la mesure où les APIs le permettent. Ne pas ajouter de sources IPTV factices ou contourner des accès.
- Exploiter les APIs publiques de Kodi/JSON-RPC/PVR plutôt que des fichiers internes MegaNexus. Pas de code ni d'assets MegaNexus repris.
- Optimiser pour les TV Android modestes (~2 Go de RAM) : chargements bornés, pagination, cache raisonnable, images peu lourdes, pas d'animations coûteuses.
- Séparer logiquement UI, accès PVR, persistance des favoris et installation. Ajouter tests unitaires sur réponses synthétiques, tests navigation/focus si environnement de simulation possible, tests ZIP/XML/manifest, compatibilité versions Kodi, et prévention des régressions du pipeline `iptv4free`.
- Si un skin Kodi GPL sert de base, respecter strictement ses licences et attributions et ne pas le confondre avec MegaNexus.
- Installer uniquement avec un plan explicite de sauvegarde, vérification, test et retour arrière. L'utilisateur doit pouvoir désinstaller IPTV4FREE tout en retrouvant Kodi et MegaNexus inchangés.

## Livraison obligatoire sur GitHub

Travaille dans **la branche et la PR #3 existantes**. Ne change pas `main` et n'ouvre pas un doublon de PR. Une fois les tests validés :
1. produire le ZIP Kodi installable avec `python3 scripts/build_addon.py` (ou adapter le script s'il faut plusieurs packages) ;
2. publier le ZIP directement dans le dépôt `dist/` sur la branche ou dans une GitHub Release publique, avec un lien direct persistant, **pas seulement un artefact GitHub Actions à durée limitée** ;
3. vérifier par l'API GitHub que le fichier existe réellement à l'URL fournie, que son contenu ZIP est valide et qu'il contient tous ses assets ;
4. mettre à jour le README avec une section concise « Installation depuis GitHub », le lien du ZIP, le chemin Kodi « Add-ons → Install from zip file », le mode de désinstallation et la manière de revenir au thème précédent ;
5. documenter les tests réellement exécutés, les limitations, les licences, et les captures d'écran réelles uniquement si une capture a été faite.

Ne déclare pas « terminé » tant que le ZIP n'est pas accessible depuis GitHub. À la fin, réponds avec : URL du fichier ZIP ; URL de PR ; modifications précises ; résultats des tests ; installation sur ma TV étape par étape ; état des essais réels ; points restant à corriger. Sois rigoureux, ne fabrique aucune réussite.
