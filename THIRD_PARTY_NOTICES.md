# Third-party notices

IPTV4FREE contains only original code, released under the MIT License (see `LICENSE`).
It bundles no third-party code, binaries or media. The components below are external:
they are installed or contacted at runtime, from their official distribution channels,
and remain under their own licenses and terms.

## Software used at runtime (not bundled)

| Component | Role | License | Obtained from |
|---|---|---|---|
| Kodi | Media center on the TV | GPL-2.0-or-later | `iptv4free setup --install-kodi` downloads the official APK from `mirrors.kodi.tv` and verifies its published SHA-256, or the user installs it from the Google Play Store |
| PVR IPTV Simple Client (`pvr.iptvsimple`) | Kodi add-on that reads the generated playlists | GPL-2.0-or-later | Installed by the user from the official Kodi add-on repository |
| inputstream.adaptive, inputstream.ffmpegdirect, inputstream.rtmp | Kodi add-ons installed as dependencies of IPTV Simple Client | GPL-2.0-or-later | Official Kodi add-on repository |
| MegaNexus (`repository.meganexus`, `plugin.video.meganexus`, `script.meganexus`, `skin.meganexus`, `screensaver.meganexus`, `vfs.meganexus`) | Optional Kodi interface | MegaNexus License (free for personal use, no redistribution); the skin GPL-2.0 with CC BY-SA 4.0 artwork, `vfs.meganexus` GPL-3.0-or-later | The user installs MegaNexus Hub in Kodi from the official MegaNexus repository; the Hub installs the other parts itself. `iptv4free meganexus setup` only downloads the repository zip to the user's computer to check it against the SHA-256 GitHub publishes |
| YouTube (`plugin.video.youtube`) | Kodi add-on used by MegaNexus' YouTube app | GPL-2.0-only | Installed by Kodi from the official Kodi add-on repository when the app is first opened |
| Android SDK Platform-Tools (`adb`) | Communication with the TV | Apache-2.0 | Installed by the user (for example `brew install android-platform-tools`) |
| Python standard library | Runtime | PSF License | Python installation |

IPTV4FREE interacts with Kodi through its public interfaces (playlist files read by IPTV
Simple Client and the Kodi JSON-RPC API), and `iptv4free meganexus rollback` writes back
Kodi's own settings files from a backup the user made. It does not include, modify or link
to Kodi or add-on code.

## Development dependencies

| Component | License |
|---|---|
| pytest | MIT |

## Data sources referenced in the example configuration

`config/example.toml` points to public URLs. Their content is downloaded by the user at
runtime and is not part of this repository.

| Source | Content | Terms |
|---|---|---|
| `iptv-org.github.io/iptv` (iptv-org/iptv project) | Public M3U playlists | The iptv-org repository is released under the Unlicense. The listed streams belong to their broadcasters and are subject to their rights and to local law. |
| `xmltvfr.fr` | French XMLTV programme guide | Terms of the site operator |
| `epgshare01.online` | XMLTV programme guides | Terms of the site operator |

IPTV4FREE does not host, provide or verify the legal status of any stream. Users are
responsible for the sources they configure and for complying with the laws and rights
that apply where they live.

The test suite uses only synthetic playlists and guides served from a local test server.

## IPTV4FREE Kodi TV interface

`kodi-addon/script.iptv4free` is original code under this project's MIT license. It ships no
fonts (Kodi uses the active skin's fonts) and no MegaNexus code or images. Its textures are the
official IPTV4FREE logo (project owner's brand artwork, `assets/branding/IPTV4FREE-original.png`)
and two generated textures (a white pixel and a blue background).

- Pillow (MIT-CMU license) is used at build and test time only, to make the 512 × 512 icon; it
  is not shipped in the add-on.
- REA (https://github.com/morluto/rea) is an optional inspection tool for a TV you own; it is
  not packaged and is not a dependency.
