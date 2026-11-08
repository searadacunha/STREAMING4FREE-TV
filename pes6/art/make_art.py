"""Generate the black/gold PES 6 TV banner and app icon.
pip install Pillow
python3 pes6/art/make_art.py
Newly drawn stylized PES 6-inspired lettering. Not an official Konami asset.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = Path(__file__).resolve().parents[1] / "res" / "drawable-nodpi"
FONTS = (
    "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-BoldOblique.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
)

def font(size):
    for name in FONTS:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.truetype("DejaVuSans-Bold.ttf", size)

def background(w, h):
    canvas = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(canvas)
    for y in range(h):
        c = round(17 - 12*y/max(1,h-1))
        d.line((0,y,w,y), fill=(c+2,c+2,c+4))
    return canvas

def word(im, text, bounds, gold):
    x0,y0,x1,y1=bounds
    d=ImageDraw.Draw(im)
    w,h=x1-x0,y1-y0
    sz=max(8,h)
    f=font(sz)
    while d.textbbox((0,0),text,font=f,stroke_width=1)[2] > w or d.textbbox((0,0),text,font=f,stroke_width=1)[3] > h:
        sz -= 1
        f = font(sz)
    bb=d.textbbox((0,0),text,font=f,stroke_width=1)
    x=x0+(w-(bb[2]-bb[0]))/2-bb[0]
    y=y0+(h-(bb[3]-bb[1]))/2-bb[1]
    d.text((x+3,y+4),text,font=f,fill="#050505",stroke_width=4,stroke_fill="#111111")
    d.text((x,y),text,font=f,
           fill=("#E5AA19" if gold else "#07090E"),
           stroke_width=3,stroke_fill=("#F4D057" if gold else "#C8982F"))

def render_banner():
    im=background(640,360)
    word(im,"PES",(40,70,420,240),False)
    word(im,"6",(430,35,600,270),True)
    d=ImageDraw.Draw(im)
    text="PRO EVOLUTION SOCCER"
    f=font(29);box=d.textbbox((0,0),text,font=f)
    d.text(((640-box[2]+box[0])/2,280),text,font=f,fill="#F3EBDD")
    d.line((190,342,450,342),fill="#9C782C",width=3)
    return im.resize((320,180),Image.Resampling.LANCZOS)

def render_icon():
    im=background(512,512)
    word(im,"6",(80,40,420,320),True)
    word(im,"PES",(36,345,475,450),False)
    return im

if __name__=="__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, im in (("banner.png",render_banner()),("ic_launcher.png",render_icon())):
        im.quantize(colors=96).save(OUT/name,optimize=True)
        print(OUT/name)
