"""Prepare the official IPTV4FREE logo for the Kodi add-on (build time only, needs Pillow).

- resources/skins/Default/media/iptv4free-logo.png: byte-for-byte copy of the original PNG.
- icon.png: 512x512 transparent square. Only invisible margins (alpha <= 1/255) are trimmed, then the
  logo is scaled proportionally and centred: no recolouring, cropping of visible pixels or distortion.
- resources/skins/Default/media/iptv4free-backdrop.png: original black/blue background texture.
- resources/skins/Default/media/iptv4free-nologo.png: neutral picture for channels without a logo.

Run after replacing assets/branding/IPTV4FREE-original.png, then commit the generated files.
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "branding" / "IPTV4FREE-original.png"
ADDON = ROOT / "kodi-addon" / "script.iptv4free"
MEDIA = ADDON / "resources" / "skins" / "Default" / "media"
HEADER = MEDIA / "iptv4free-logo.png"
ICON = ADDON / "icon.png"
BACKDROP = MEDIA / "iptv4free-backdrop.png"
NOLOGO = MEDIA / "iptv4free-nologo.png"
ICON_SIZE, ICON_BOX = 512, 488  # 12 px transparent safety margin on each side


def _pil():
    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit("Install the build-time dependency: python3 -m pip install pillow") from exc
    return Image


def make_icon(source: Path, icon: Path) -> None:
    Image = _pil()
    with Image.open(source) as original:
        if original.format != "PNG":
            raise SystemExit(f"Expected the unmodified PNG logo: {source}")
        logo = original.convert("RGBA")
    # Smallest box holding every visible pixel; alpha 1/255 is stray noise reaching the corners.
    box = logo.getchannel("A").point(lambda v: 255 if v > 1 else 0).getbbox()
    if box:
        logo = logo.crop(box)
    scale = min(ICON_BOX / logo.width, ICON_BOX / logo.height)
    logo = logo.resize((max(1, round(logo.width * scale)), max(1, round(logo.height * scale))),
                       Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    canvas.alpha_composite(logo, ((ICON_SIZE - logo.width) // 2, (ICON_SIZE - logo.height) // 2))
    icon.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(icon, format="PNG", optimize=True)


def make_backdrop(path: Path) -> None:
    """Small radial glow (electric blue into black); Kodi stretches it to 1920x1080 smoothly."""
    Image = _pil()
    w, h = 192, 108
    img = Image.new("RGB", (w, h))
    for y in range(h):
        for x in range(w):
            d = min(1.0, (((x - w * 0.78) / w) ** 2 + ((y + h * 0.1) / h) ** 2) ** 0.5 * 1.25)
            k = (1 - d) ** 2
            img.putpixel((x, y), (round(2 + 6 * k), round(3 + 14 * k), round(8 + 70 * k)))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG", optimize=True)


def make_nologo(path: Path) -> None:
    """Neutral TV outline shown for channels without a logo (drawn 4x, then downscaled)."""
    Image = _pil()
    from PIL import ImageDraw
    k, colour = 4, (110, 124, 160, 255)
    img = Image.new("RGBA", (200 * k, 125 * k), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((40 * k, 28 * k, 160 * k, 108 * k), radius=12 * k, outline=colour, width=6 * k)
    draw.line((84 * k, 28 * k, 70 * k, 10 * k), fill=colour, width=5 * k)
    draw.line((116 * k, 28 * k, 130 * k, 10 * k), fill=colour, width=5 * k)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.resize((200, 125), Image.Resampling.LANCZOS).save(path, format="PNG", optimize=True)


def prepare_logo(*, source: Path = SOURCE, header: Path = HEADER, icon: Path = ICON) -> bool:
    """Return False when the official logo has not been added yet (text header stays)."""
    if not source.is_file():
        print(f"Official logo missing: {source} (keeping the text header)")
        return False
    make_icon(source, icon)
    header.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != header.resolve():
        shutil.copyfile(source, header)  # exact on-screen artwork
    print(f"Prepared IPTV4FREE logo: {header}; Kodi icon: {icon}")
    return True


if __name__ == "__main__":
    prepare_logo()
    make_backdrop(BACKDROP)
    make_nologo(NOLOGO)
