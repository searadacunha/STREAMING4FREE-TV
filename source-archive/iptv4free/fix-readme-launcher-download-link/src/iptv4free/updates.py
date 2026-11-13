"""Persistent state and change control: scan history, stable channel numbers, changesets."""
from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .playlists import Entry, kodi_identity


def atomic_write(path: Path, data: str | bytes) -> None:
    """Write to a temporary file in the same directory, then rename over the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = data.encode("utf-8") if isinstance(data, str) else data
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


class ScanHistory:
    """Per-stream scan outcomes. A stream stays in the lineup until it has failed
    `max_failed` scans in a row, so one flaky scan does not remove and re-add channels."""

    def __init__(self, path: Path):
        self.path = path
        self.streams: dict[str, dict] = _load_json(path, {})

    def record(self, key: str, ok: bool, detail: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        s = self.streams.setdefault(key, {"last_ok": None, "fail_streak": 0})
        s["checked"], s["detail"] = now, detail
        if ok:
            s["last_ok"], s["fail_streak"] = now, 0
        else:
            s["fail_streak"] += 1

    def alive(self, key: str, max_failed: int) -> bool:
        s = self.streams.get(key)
        return bool(s and s["last_ok"] is not None and s["fail_streak"] < max_failed)

    def save(self) -> None:
        atomic_write(self.path, json.dumps(self.streams, indent=0, sort_keys=True))


class NumberBook:
    """Channel numbers that survive rebuilds: a channel keeps its number while it exists
    and gets it back if it returns. New channels take the next free number."""

    def __init__(self, path: Path):
        self.path = path
        self.book: dict[str, dict[str, int]] = _load_json(path, {})
        self._top = {lineup: max(nums.values(), default=0) for lineup, nums in self.book.items()}

    def assign(self, lineup: str, key: str, floor: int) -> int:
        numbers = self.book.setdefault(lineup, {})
        if key not in numbers:
            numbers[key] = max(floor - 1, self._top.get(lineup, 0)) + 1
            self._top[lineup] = numbers[key]
        return numbers[key]

    def save(self) -> None:
        atomic_write(self.path, json.dumps(self.book, indent=0, sort_keys=True))


@dataclass
class Changeset:
    added: list[str]
    removed: list[str]
    kept: int
    old_count: int
    new_count: int

    @property
    def size(self) -> int:
        """Rows Kodi has to delete or insert in its channel database."""
        return len(self.added) + len(self.removed)


def changeset(old: list[Entry], new: list[Entry]) -> Changeset:
    old_ids = {kodi_identity(e) for e in old}
    new_ids = {kodi_identity(e) for e in new}
    return Changeset(
        added=sorted(new_ids - old_ids), removed=sorted(old_ids - new_ids),
        kept=len(old_ids & new_ids), old_count=len(old_ids), new_count=len(new_ids))
