"""Prepare exact user-supplied IPTV4FREE logo for Kodi UI and application icon.

The original uploaded PNG must be committed to assets/branding/IPTV4FREE-original.png
before generating branded files. No original pixels are changed for the on-screen logo.
Pillow is used only when building the icon, not inside Kodi at runtime.
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "branding" / "IPTV4FREE-original.png"
ADDON = ROOT / "kodi-addon" / "script.iptv4free"
HEADER = ADDON / "resources" / "skins" / "Default" / "media" / "iptv4free-logo.png"
ICON = ADDON / "icon.png"


def prepare_logo(*, source: Path = SOURCE, header: Path = HEADER, icon: Path = ICON) -> bool:
    """Return False if no source uploaded. When present, package exact PNG + icon."""
    if not source.is_file():
        print(f"Brand image not uploaded yet: {source} (keeping text header)")
        return False
    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit("Install build-time dependency: python3 -m pip install pillow") from exc

    with Image.open(source) as original:
        if original.format != "PNG":
            raise SystemExit(f"Expected unmodified PNG: {source}")
        original.load()
        scaled = original.convert("RGBA")
        scaled.thumbnail((488, 488), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        canvas.alpha_composite(scaled, ((512 - scaled.width) // 2, (512 - scaled.height) // 2))

    header.parent.mkdir(parents=True, exist_ok=True)
    icon.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != header.resolve():
        shutil.copyfile(source, header)  # byte-for-byte exact on-screen artwork
    canvas.save(icon, format="PNG", optimize=True)
    print(f"Prepared IPTV4FREE logo: {header}; Kodi icon: {icon}")
    return True


if __name__ == "__main__":
    prepare_logo()
