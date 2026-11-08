"""Configuration file (TOML) loading and validation."""
from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# iptv-org category -> group shown in Kodi, in display order. Overridable with [categories].
DEFAULT_CATEGORY_GROUPS: dict[str, list[str]] = {
    "News": ["News", "Business", "Weather", "Legislative"],
    "General": ["General", "Entertainment", "Public", "Interactive"],
    "Sports": ["Sports", "Outdoor"],
    "Movies & Series": ["Movies", "Series", "Classic", "Comedy"],
    "Kids": ["Kids", "Animation", "Family"],
    "Documentary": ["Documentary", "Science", "Travel", "Culture", "Education", "Auto",
                    "Cooking", "Lifestyle", "Relax"],
    "Music": ["Music"],
    "Religious": ["Religious"],
}
RESTART_POLICIES = ("auto", "always", "never")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Lineup:
    id: str
    name: str
    sources: tuple[str, ...]
    epg: str = ""
    favorites: tuple[str, ...] = ()
    first_number: int = 1
    by_category: bool = False
    exclude_categories: tuple[str, ...] = ()
    epg_aliases: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Config:
    path: Path
    lineups: tuple[Lineup, ...]
    # [tv]
    tv_address: str = ""
    adb: str = "adb"
    remote_dir: str = "/sdcard/Download/iptv4free"
    kodi_package: str = "org.xbmc.kodi"
    jsonrpc_port: int = 9090
    forward_port: int = 19090
    adb_timeout: float = 30.0
    relay: bool = False  # route measured channels through the add-on's relay (add-on 0.4.0+ on the TV)
    # [paths]
    state_dir: Path = Path("~/.local/state/iptv4free").expanduser()
    output_dir: Path = Path("build")
    # [scan]
    scan_timeout: float = 8.0
    scan_workers: int = 32
    user_agent: str = "Kodi/21.3 (Linux; Android 12) iptv4free"
    max_failed_scans: int = 3
    epg_max_age_hours: float = 12.0
    # [safety]
    max_changes: int = 500
    min_keep_ratio: float = 0.5
    backups: int = 5
    restart_kodi: str = "auto"
    # [labels]
    favorites_label: str = "Favorites"
    all_label: str = "All"
    other_label: str = "Other"
    category_groups: dict[str, list[str]] = field(
        default_factory=lambda: dict(DEFAULT_CATEGORY_GROUPS))

    def remote_path(self, lineup: Lineup) -> str:
        return f"{self.remote_dir.rstrip('/')}/{lineup.id}.m3u"

    def kodi_path(self, lineup: Lineup) -> str:
        """Path to type into Kodi: /sdcard is a symlink apps may not resolve."""
        path = self.remote_path(lineup)
        return "/storage/emulated/0" + path[len("/sdcard"):] if path.startswith("/sdcard/") else path


def _get(table: dict, key: str, kind: type, default):
    value = table.get(key, default)
    if kind is float and isinstance(value, int) and not isinstance(value, bool):
        value = float(value)
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise ConfigError(f"'{key}' must be of type {kind.__name__}, got {value!r}")
    return value


def _str_list(table: dict, key: str) -> tuple[str, ...]:
    value = table.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"'{key}' must be a list of strings")
    return tuple(value)


def _lineup(raw: dict) -> Lineup:
    lid = _get(raw, "id", str, "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", lid):
        raise ConfigError(f"lineup id {lid!r} must be lowercase letters, digits, '-' or '_'")
    sources = _str_list(raw, "sources")
    if not sources:
        raise ConfigError(f"lineup '{lid}' has no sources")
    aliases = raw.get("epg_aliases", {})
    if not isinstance(aliases, dict) or not all(isinstance(v, str) for v in aliases.values()):
        raise ConfigError(f"lineup '{lid}': epg_aliases must map names to EPG channel ids")
    first = _get(raw, "first_number", int, 1)
    if first < 1:
        raise ConfigError(f"lineup '{lid}': first_number must be >= 1")
    return Lineup(
        id=lid, name=_get(raw, "name", str, lid.title()), sources=sources,
        epg=_get(raw, "epg", str, ""), favorites=_str_list(raw, "favorites"),
        first_number=first, by_category=_get(raw, "by_category", bool, False),
        exclude_categories=_str_list(raw, "exclude_categories"), epg_aliases=dict(aliases))


def load_config(path: str | os.PathLike) -> Config:
    path = Path(path).expanduser().resolve()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}") from None
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from None

    tv, paths, scan = data.get("tv", {}), data.get("paths", {}), data.get("scan", {})
    safety, labels = data.get("safety", {}), data.get("labels", {})
    raw_lineups = data.get("lineup", [])
    if not raw_lineups:
        raise ConfigError("at least one [[lineup]] is required")
    lineups = tuple(_lineup(r) for r in raw_lineups)
    ids = [lu.id for lu in lineups]
    if len(set(ids)) != len(ids):
        raise ConfigError(f"duplicate lineup ids: {ids}")

    base = path.parent

    def local_path(value: str) -> Path:
        p = Path(value).expanduser()
        return p if p.is_absolute() else base / p

    groups = data.get("categories", DEFAULT_CATEGORY_GROUPS)
    if not isinstance(groups, dict) or not all(
            isinstance(v, list) and all(isinstance(c, str) for c in v) for v in groups.values()):
        raise ConfigError("[categories] must map group names to lists of source categories")

    cfg = Config(
        path=path, lineups=lineups,
        tv_address=os.environ.get("IPTV4FREE_TV") or _get(tv, "address", str, ""),
        adb=os.environ.get("IPTV4FREE_ADB") or _get(tv, "adb", str, "adb"),
        remote_dir=_get(tv, "remote_dir", str, "/sdcard/Download/iptv4free"),
        kodi_package=_get(tv, "kodi_package", str, "org.xbmc.kodi"),
        jsonrpc_port=_get(tv, "jsonrpc_port", int, 9090),
        forward_port=_get(tv, "forward_port", int, 19090),
        adb_timeout=_get(tv, "adb_timeout", float, 30.0),
        relay=_get(tv, "relay", bool, False),
        state_dir=local_path(_get(paths, "state_dir", str, "~/.local/state/iptv4free")),
        output_dir=local_path(_get(paths, "output_dir", str, "build")),
        scan_timeout=_get(scan, "timeout", float, 8.0),
        scan_workers=_get(scan, "workers", int, 32),
        user_agent=_get(scan, "user_agent", str, Config.user_agent),
        max_failed_scans=_get(scan, "max_failed_scans", int, 3),
        epg_max_age_hours=_get(scan, "epg_max_age_hours", float, 12.0),
        max_changes=_get(safety, "max_changes", int, 500),
        min_keep_ratio=_get(safety, "min_keep_ratio", float, 0.5),
        backups=_get(safety, "backups", int, 5),
        restart_kodi=_get(safety, "restart_kodi", str, "auto"),
        favorites_label=_get(labels, "favorites", str, "Favorites"),
        all_label=_get(labels, "all", str, "All"),
        other_label=_get(labels, "other", str, "Other"),
        category_groups={k: list(v) for k, v in groups.items()},
    )
    if cfg.restart_kodi not in RESTART_POLICIES:
        raise ConfigError(f"restart_kodi must be one of {RESTART_POLICIES}")
    if cfg.scan_workers < 1 or cfg.scan_timeout <= 0 or cfg.max_failed_scans < 1:
        raise ConfigError("scan: workers >= 1, timeout > 0 and max_failed_scans >= 1 required")
    if cfg.max_changes < 0 or not 0 <= cfg.min_keep_ratio <= 1 or cfg.backups < 1:
        raise ConfigError("safety: max_changes >= 0, 0 <= min_keep_ratio <= 1, backups >= 1")
    if not cfg.remote_dir.startswith("/"):
        raise ConfigError("tv.remote_dir must be an absolute path on the TV")
    return cfg
