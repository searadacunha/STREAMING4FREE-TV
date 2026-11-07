"""Generates the CINEFUSE TV banner (320x180, xhdpi) and square icon in res/.
Needs Pillow and macOS (Avenir Next Condensed system font): python3 make_art.py"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

RES = Path(__file__).parent / "res"
FONT_FILE = next(p for p in ("/System/Library/Fonts/Avenir Next Condensed.ttc",  # macOS 14
                             "/System/Library/Fonts/Supplemental/Avenir Next Condensed.ttc") if Path(p).exists())
FONT = ImageFont.truetype(FONT_FILE, 10, index=0)  # Bold
WHITE = (255, 255, 255, 255)
BLUE = (30, 120, 255)
SS = 8  # supersampling, then Lanczos downscale


def art(w, h, runs, text_w_ratio, line_y_ratio):
    """runs: [(text, RGBA colour)] drawn on one letter-spaced line, centred."""
    W, H = w * SS, h * SS
    # deep black background, slight vertical gradient
    bg = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / H
        c = int(10 - 7 * t)
        d.line([(0, y), (W, y)], fill=(c, c, c + 2))
    # very faint blue glow under the word
    glow = Image.new("L", (W, H))
    ImageDraw.Draw(glow).ellipse([W * 0.2, H * 0.62, W * 0.8, H * 1.15], fill=38)
    glow = glow.filter(ImageFilter.GaussianBlur(W * 0.08))
    bg.paste(Image.new("RGB", (W, H), BLUE), mask=glow)

    chars = [(ch, col) for text, col in runs for ch in text]
    size = 100
    track = 0.12  # letter spacing as a fraction of the font size
    width = lambda f, s: sum(f.getlength(ch) for ch, _ in chars) + s * track * (len(chars) - 1)
    font = FONT.font_variant(size=size)
    size = int(size * (W * text_w_ratio) / width(font, size))
    font = FONT.font_variant(size=size)
    tw = width(font, size)
    cap_top, cap_bot = font.getbbox("H")[1], font.getbbox("H")[3]
    cap_h = cap_bot - cap_top
    x = (W - tw) / 2
    y = (H - cap_h) / 2 - cap_top - H * 0.03
    layer = Image.new("RGBA", (W, H))
    ld = ImageDraw.Draw(layer)
    for ch, col in chars:
        if ch != " ":
            ld.text((x, y), ch, font=font, fill=col)
        x += font.getlength(ch) + size * track
    bg.paste(layer, mask=layer)

    # electric blue rule under the word, with a soft glow
    lw, lh = tw * 0.24, max(SS * 2, int(H * 0.012))
    ly = (H + cap_h) / 2 - H * 0.03 + H * line_y_ratio
    box = [(W - lw) / 2, ly, (W + lw) / 2, ly + lh]
    halo = Image.new("L", (W, H))
    ImageDraw.Draw(halo).rectangle(box, fill=150)
    halo = halo.filter(ImageFilter.GaussianBlur(lh * 2))
    bg.paste(Image.new("RGB", (W, H), BLUE), mask=halo)
    ImageDraw.Draw(bg).rectangle(box, fill=(70, 150, 255))
    return bg.resize((w, h), Image.LANCZOS)


def save(img, rel):
    p = RES / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(p, optimize=True)
    print(p.relative_to(RES.parent), img.size)


if __name__ == "__main__":
    save(art(320, 180, [("CINEFUSE", WHITE), (" TV", BLUE + (255,))], 0.74, 0.09), "drawable-xhdpi/banner.png")
    master = art(512, 512, [("CF", WHITE)], 0.56, 0.07)  # "CINEFUSE" is unreadable at 48 px
    for dpi, px in {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}.items():
        save(master.resize((px, px), Image.LANCZOS), f"mipmap-{dpi}/ic_launcher.png")
