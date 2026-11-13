"""Safe playlist deployment to the TV, with backups and rollback.

The playlists on the TV are the baseline: each run pulls them, computes what Kodi would
delete or insert, and refuses large changes unless explicitly allowed. Files are uploaded
under a temporary name, checksummed on the TV, then renamed over the old ones.
"""
from __future__ import annotations

import hashlib
import logging
import shlex
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from .adb import Adb
from .channels import validate
from .config import Config
from .kodi import restart
from .playlists import parse_m3u
from .updates import Changeset, changeset

log = logging.getLogger(__name__)

EXIT_REFUSED = 3


class DeployError(RuntimeError):
    pass


@dataclass
class Plan:
    files: dict[str, Path]                              # lineup id -> local playlist to upload
    current: dict[str, Path | None]                     # lineup id -> pulled TV copy (None: absent)
    changes: dict[str, Changeset] = field(default_factory=dict)
    unchanged: list[str] = field(default_factory=list)  # identical bytes already on the TV

    @property
    def total(self) -> int:
        return sum(c.size for c in self.changes.values())


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_entries(path: Path | None):
    return [] if path is None else parse_m3u(path.read_text(encoding="utf-8")).entries


def plan(config: Config, adb: Adb, files: dict[str, Path], workdir: Path) -> Plan:
    """Pull the TV's current playlists and diff them against `files`."""
    p = Plan(files=files, current={})
    for lineup in config.lineups:
        if lineup.id not in files:
            continue
        remote = config.remote_path(lineup)
        local_copy = workdir / f"{lineup.id}.current.m3u"
        if adb.exists(remote):
            adb.pull(remote, str(local_copy))
            p.current[lineup.id] = local_copy
        else:
            p.current[lineup.id] = None
        if p.current[lineup.id] and _sha(local_copy) == _sha(files[lineup.id]):
            p.unchanged.append(lineup.id)
            continue
        p.changes[lineup.id] = changeset(_read_entries(p.current[lineup.id]),
                                         _read_entries(files[lineup.id]))
    return p


def check(config: Config, p: Plan, allow_large: bool) -> list[str]:
    """Reasons to refuse this plan. Empty list: safe to apply."""
    problems = []
    for lid, path in p.files.items():
        problems += [f"{lid}: {msg}" for msg in validate(_read_entries(path))]
    if allow_large:
        return problems
    first_import = p.changes and all(p.current.get(lid) is None for lid in p.changes)
    if p.total > config.max_changes and first_import:
        problems.append(
            f"first deployment: {p.total} channels will be imported into Kodi, above "
            f"safety.max_changes ({config.max_changes}). Re-run with --allow-large-update")
    elif p.total > config.max_changes:
        problems.append(
            f"{p.total} channel additions/removals exceed safety.max_changes "
            f"({config.max_changes}). Kodi rebuilds its channel database for each one and a "
            "low-memory TV can freeze for a long time. Re-run with --allow-large-update when "
            "nobody is watching, or raise max_changes")
    for lid, c in p.changes.items():
        if c.old_count and c.new_count < c.old_count * config.min_keep_ratio:
            problems.append(
                f"{lid}: would shrink from {c.old_count} to {c.new_count} channels (below "
                f"safety.min_keep_ratio {config.min_keep_ratio}). A failed scan or network "
                "outage looks like this; use --allow-large-update if it is intended")
    return problems


def summary(p: Plan) -> str:
    lines = []
    for lid in p.unchanged:
        lines.append(f"  {lid}: unchanged")
    for lid, c in p.changes.items():
        lines.append(f"  {lid}: {c.old_count} -> {c.new_count} channels, "
                     f"+{len(c.added)} added, -{len(c.removed)} removed, {c.kept} kept")
    lines.append(f"  total database changes: {p.total}")
    return "\n".join(lines)


def _backup(config: Config, p: Plan) -> Path | None:
    existing = {lid: path for lid, path in p.current.items() if path and lid in p.changes}
    if not existing:
        return None
    root = config.state_dir / "backups"
    dest = root / time.strftime("%Y%m%d-%H%M%S")
    n = 1
    while dest.exists():
        n += 1
        dest = root / f"{time.strftime('%Y%m%d-%H%M%S')}-{n}"
    dest.mkdir(parents=True)
    for lid, path in existing.items():
        shutil.copy2(path, dest / f"{lid}.m3u")
    for old in sorted(d for d in root.iterdir() if d.is_dir())[:-config.backups]:
        shutil.rmtree(old)
    return dest


def _upload(config: Config, adb: Adb, lineup_id: str, local: Path) -> None:
    lineup = next(lu for lu in config.lineups if lu.id == lineup_id)
    remote = config.remote_path(lineup)
    tmp = remote + ".uploading"
    adb.push(str(local), tmp)
    remote_sha = adb.sha256(tmp)
    if remote_sha != _sha(local):
        adb.shell(f"rm -f {shlex.quote(tmp)}", check=False)
        raise DeployError(f"{lineup_id}: upload corrupted (checksum mismatch); TV file untouched")
    adb.shell(f"mv -f {shlex.quote(tmp)} {shlex.quote(remote)}")


def apply(config: Config, adb: Adb, files: dict[str, Path], *, dry_run: bool = False,
          allow_large: bool = False, restart_policy: str | None = None,
          out=print) -> int:
    """Deploy `files` (lineup id -> local playlist). Returns a process exit code."""
    adb.connect()
    with tempfile.TemporaryDirectory(prefix="iptv4free-") as tmp:
        p = plan(config, adb, files, Path(tmp))
        out("Deployment plan:\n" + summary(p))
        problems = check(config, p, allow_large)
        if problems:
            for msg in problems:
                out(f"REFUSED: {msg}")
            out("Nothing was changed on the TV.")
            return EXIT_REFUSED
        if not p.changes:
            out("TV already up to date.")
            return 0
        if dry_run:
            out("Dry run: nothing was changed on the TV.")
            return 0
        backup = _backup(config, p)
        if backup:
            out(f"Backup of the previous playlists: {backup}")
        adb.shell(f"mkdir -p {shlex.quote(config.remote_dir)}")
        for lid in p.changes:
            _upload(config, adb, lid, p.files[lid])
            out(f"  {lid}: uploaded")
    out(restart(adb, config, restart_policy or config.restart_kodi))
    return 0


def backups(config: Config) -> list[Path]:
    root = config.state_dir / "backups"
    return sorted(d for d in root.iterdir() if d.is_dir()) if root.exists() else []


def rollback(config: Config, adb: Adb, name: str | None = None, *, dry_run: bool = False,
             restart_policy: str | None = None, out=print) -> int:
    """Put back the playlists saved before a deployment (the latest one by default)."""
    available = backups(config)
    if not available:
        out("No backup available.")
        return 1
    chosen = next((b for b in available if b.name == name), None) if name else available[-1]
    if chosen is None:
        out(f"Backup {name!r} not found. Available: {', '.join(b.name for b in available)}")
        return 1
    out(f"Rolling back to {chosen.name}")
    with tempfile.TemporaryDirectory(prefix="iptv4free-rollback-") as tmp:
        # work on a copy: the backup taken during apply may prune the one being restored
        files = {}
        for f in sorted(chosen.glob("*.m3u")):
            if f.stem in {lu.id for lu in config.lineups}:
                files[f.stem] = Path(shutil.copy2(f, Path(tmp) / f.name))
        # restoring a known state may exceed max_changes; it is still validated and shown
        return apply(config, adb, files, dry_run=dry_run, allow_large=True,
                     restart_policy=restart_policy, out=out)
