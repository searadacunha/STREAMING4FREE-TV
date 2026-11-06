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
  installed from their official distribution channels.
- Write commit messages that say what changed and why.

## Reporting a bug

Include the output of `iptv4free -v doctor`, the command that failed, and the last lines of
`~/.local/state/iptv4free/iptv4free.log`. Remove IP addresses and private playlist URLs first.
