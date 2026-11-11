"""Generates the STREAMING4FREE TV banner (320x180, xhdpi) and square icon in src/main/res/.
Same look as the WATCHED and CINEFUSE TV tiles: it reuses cinefuse/make_art.py. Needs Pillow and macOS."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cinefuse"))
from make_art import BLUE, WHITE, art  # noqa: E402
from PIL import Image  # noqa: E402

RES = Path(__file__).parent / "src" / "main" / "res"
ACCENT = BLUE + (255,)


def save(img, rel):
    p = RES / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(p, optimize=True)
    print(p.relative_to(RES.parent.parent.parent), img.size)


if __name__ == "__main__":
    save(art(320, 180, [("STREAMING", WHITE), ("4", ACCENT), ("FREE", WHITE)], 0.84, 0.09), "drawable-xhdpi/banner.png")
    master = art(512, 512, [("S", WHITE), ("4", ACCENT), ("F", WHITE)], 0.62, 0.07)
    for dpi, px in {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}.items():
        save(master.resize((px, px), Image.LANCZOS), f"mipmap-{dpi}/ic_launcher.png")
