# Original IPTV4FREE releases

## v0.2.0 — IPTV4FREE 0.2.0

Published: 2026-11-07T08:29:38Z. Target: `55cfbf6acab5d88cc05203779062c1d67e4cc634`.

## IPTV4FREE 0.2.0

Optional support for [MegaNexus](https://github.com/MegaNexusMediaPlayer/MegaNexus), a
third-party Kodi interface. MegaNexus is not bundled or redistributed: Kodi installs it from
the official MegaNexus repository.

### New

- `iptv4free meganexus doctor`: read-only checks (native build for the TV's CPU, RAM,
  storage, Kodi 21/22, MegaNexus add-ons and versions, skin, channel count, Kodi memory; a
  Kodi that runs but does not answer is reported as frozen).
- `iptv4free meganexus setup`: backs up Kodi's settings and the deployed playlists, checks
  the repository zip on the official source against the SHA-256 GitHub publishes for the
  latest MegaNexus release, prints the installation steps.
- `iptv4free meganexus rollback`: restores the settings files changed since the backup and
  disables MegaNexus; refuses during playback; `--force` restarts a frozen Kodi; `--dry-run`,
  `--list`, `--backup`.

### How it fits

MegaNexus' Channels screen reads Kodi's own TV channels, so the lineups deployed to IPTV
Simple Client appear there with their groups and guide, without a second import.
`iptv4free deploy` stays the only update path.

### Tested

67 tests (Ubuntu and macOS, Python 3.11 to 3.13). On one Android 12 TV (32-bit ARM, 1.8 GB,
Kodi 21.3, MegaNexus 9.1.0, 7,883 channels): installation, HUB, Home, Search, YouTube,
Channels with playback, restarts and `rollback --force`. Problems seen on that TV are listed
under Limitations in the README.


