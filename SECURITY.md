# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub:
**Security > Report a vulnerability** on this repository. Do not open a public issue.
Expect an acknowledgement within a week.

## Security model

- IPTV4FREE runs on your computer and talks to the TV over ADB. ADB grants full control of
  the TV: enable network debugging only on a trusted local network, and turn it off when
  you no longer need it.
- Kodi's JSON-RPC port (9090) is reached through `adb forward`; IPTV4FREE never asks Kodi to
  listen on the network.
- Stream probes verify TLS certificates. Playlists and XMLTV guides are untrusted input:
  they are parsed defensively, and nothing in them is executed.
- The Kodi APK is downloaded only from `mirrors.kodi.tv` and installed only if its SHA-256
  matches the checksum published next to it.
- The MegaNexus repository zip is used only if the copy on the official source matches the
  SHA-256 GitHub publishes for the latest MegaNexus release.
- `iptv4free meganexus setup` copies Kodi's settings to `~/.local/state/iptv4free/meganexus/backups/`.
  Once you sign in to accounts or enter API keys in Kodi add-ons, these backups contain them:
  keep them private. `rollback` only replaces settings files that already exist on the TV,
  never while Kodi is playing.
- `scripts/serve_addon.py` serves only the `dist/` folder, to the whole local network, while
  it runs: stop it (Ctrl+C) once Kodi has installed the add-on. Installing a ZIP requires
  Kodi's "Unknown sources" setting; install only ZIPs you built or downloaded from this
  repository.
- The TV interface add-on only calls Kodi's local JSON-RPC from inside Kodi, opens no network
  port, and stores only favourite channel names in its add-on data folder.
- No credentials are needed or stored. If you use private playlists that contain access
  tokens, keep them in your own `iptv4free.toml`, which is excluded from version control.
  Logs and state files (`~/.local/state/iptv4free/`) may contain stream URLs: do not publish them.
