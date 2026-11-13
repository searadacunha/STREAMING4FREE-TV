# Contributing

Bug reports and pull requests are welcome.

## Development setup

```bash
git clone https://github.com/searadacunha/IPTV4FREE.git
cd IPTV4FREE
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The test suite needs no TV and no Internet access: it uses a local HTTP server, a fake
`adb` (`tests/fake_adb.py`) and a fake Kodi JSON-RPC server (`tests/conftest.py`).

## Guidelines

- Keep the runtime free of third-party dependencies (Python 3.11+ standard library only).
- Every behaviour change needs a test. Changes to `deploy.py` or `updates.py` must keep the
  safety guarantees: no upload without a plan, no plan above `max_changes` without an explicit
  override, atomic uploads, a backup before every change.
- Never commit real playlists, stream URLs with tokens, TV addresses, logs or `iptv4free.toml`.
- Do not add third-party code or binaries to the repository. Kodi and its add-ons are
  installed from their official distribution channels. MegaNexus' license forbids
  redistributing or adapting its code: `meganexus.py` relies only on its documentation and on
  Kodi's public interfaces.
- `meganexus.py` must keep its guarantees: a backup before any change, no rollback while Kodi
  plays, no forced stop of a Kodi that still runs without `--force`.
- The Kodi add-on (`kodi-addon/script.iptv4free/`) is Python standard library only, and
  `resources/lib/core.py` must stay free of Kodi imports so it can be tested. Use font names
  that Kodi skins define (Kodi ignores fonts shipped by an add-on) and texture names starting
  with `iptv4free-`. Bump the version in `addon.xml` for every published ZIP.
- Never edit or regenerate the official logo (`assets/branding/IPTV4FREE-original.png`). If it
  is replaced by the project owner, run `scripts/prepare_branding.py`, then
  `scripts/build_addon.py`, and commit the generated files and the ZIP in `dist/`. The ZIP is
  reproducible: CI rebuilds it and fails if its content is incomplete.
- Write commit messages that say what changed and why.

## Reporting a bug

Include the output of `iptv4free -v doctor`, the command that failed, and the last lines of
`~/.local/state/iptv4free/iptv4free.log`. Remove IP addresses and private playlist URLs first.
