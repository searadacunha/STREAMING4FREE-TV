"""Build the installable Kodi ZIP of IPTV4FREE's TV interface from the committed add-on files.

The archive is reproducible (stored, fixed dates, sorted), so a local build and the GitHub
Actions build are byte-identical. Run scripts/prepare_branding.py first when the logo changes.
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "kodi-addon" / "script.iptv4free"
REQUIRED = ["addon.xml", "default.py", "icon.png", "resources/lib/core.py",
            "resources/skins/Default/1080i/IPTV4FREE.xml",
            "resources/skins/Default/media/iptv4free-logo.png",
            "resources/skins/Default/media/iptv4free-pixel.png",
            "resources/skins/Default/media/iptv4free-backdrop.png"]


def build(out_dir: Path = ROOT / "dist") -> Path:
    missing = [p for p in REQUIRED if not (SRC / p).is_file()]
    if missing:
        raise SystemExit(f"Missing add-on files: {', '.join(missing)}")
    version = ET.parse(SRC / "addon.xml").getroot().get("version")
    out = out_dir / f"{SRC.name}-{version}.zip"
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in SRC.rglob("*") if p.is_file()
                   and "__pycache__" not in p.parts and p.suffix != ".pyc" and p.name != ".DS_Store")
    with ZipFile(out, "w", compression=ZIP_STORED) as archive:
        for path in files:
            info = ZipInfo(path.relative_to(SRC.parent).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    return out


if __name__ == "__main__":
    zip_path = build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist")
    print(f"Created {zip_path} ({zip_path.stat().st_size:,} bytes)")
