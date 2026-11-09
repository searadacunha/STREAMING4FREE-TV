"""Build Android TV banner/icon using the official, unmodified IPTV4FREE source logo.

Source bytes are never overwritten. Build derivatives are resized proportionally; the splash
uses a byte-for-byte copy of the original file.
Requires Pillow for build-time only, not at runtime on the TV.
"""
import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "assets/branding/IPTV4FREE-original.png"
OUT = ROOT / "android-tv-launcher/app/src/main/res/drawable-nodpi"


def visible_logo():
    image = Image.open(ORIGINAL).convert("RGBA")
    alpha = image.getchannel("A")
    bbox = alpha.point(lambda a: 255 if a > 1 else 0).getbbox()
    return image.crop(bbox) if bbox else image


def make_fit(image, canvas_size, fraction):
    w, h = canvas_size
    max_w, max_h = int(w * fraction), int(h * fraction)
    scale = min(max_w / image.width, max_h / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    art = image.resize(size, Image.Resampling.LANCZOS)
    return art, ((w - size[0]) // 2, (h - size[1]) // 2)


def main():
    logo = visible_logo()
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ORIGINAL, OUT / "iptv4free_logo_original.png")

    icon = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    art, point = make_fit(logo, (512, 512), 0.88)
    icon.alpha_composite(art, point)
    icon.save(OUT / "iptv4free_launcher_icon.png", optimize=True)

    banner = Image.new("RGBA", (320, 180), (5, 8, 23, 255))
    art, point = make_fit(logo, (320, 180), 0.91)
    banner.alpha_composite(art, point)
    banner.convert("RGB").save(OUT / "iptv4free_tv_banner.png", optimize=True)
    print("Android TV logo/icon ready; original source unchanged.")


if __name__ == "__main__":
    main()
