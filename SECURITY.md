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
- No credentials are needed or stored. If you use private playlists that contain access
  tokens, keep them in your own `iptv4free.toml`, which is excluded from version control.
  Logs and state files (`~/.local/state/iptv4free/`) may contain stream URLs: do not publish them.
