"""Build a standalone Kodi ZIP of IPTV4FREE's original TV interface."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from prepare_branding import prepare_logo

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "kodi-addon" / "script.iptv4free"
OUT = ROOT / "dist" / "script.iptv4free-0.1.0.zip"

if not (SRC / "addon.xml").is_file():
    raise SystemExit("Missing Kodi addon.xml")
prepare_logo()
OUT.parent.mkdir(parents=True, exist_ok=True)
with ZipFile(OUT, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
    for path in sorted(SRC.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            archive.write(path, path.relative_to(SRC.parent).as_posix())
print(f"Created {OUT} ({OUT.stat().st_size:,} bytes)")
