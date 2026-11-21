"""Generate the app icon (PNG, .icns on macOS, .ico) and the DMG background into assets/.

    uv run python packaging/make_icon.py
The mark: a Northwestern-purple tile, a mortarboard (the course) over a Purple Line route with
three stations (the line, and the seat at the end station).
"""
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).resolve().parent.parent / "assets"
PURPLE = (78, 42, 132, 255)
WHITE = (255, 255, 255, 255)
GREEN = (76, 200, 138, 255)
S = 4096  # supersample canvas


def icon(size: int = 1024) -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = int(S * 0.098)  # macOS icon grid: art sits inside an ~824/1024 tile
    d.rounded_rectangle((pad, pad, S - pad, S - pad), radius=int((S - 2 * pad) * 0.2237), fill=PURPLE)

    cx = S // 2
    # mortarboard: diamond top + band + tassel
    top = int(S * 0.27)
    w, h = int(S * 0.27), int(S * 0.115)
    d.polygon([(cx, top), (cx + w, top + h), (cx, top + 2 * h), (cx - w, top + h)], fill=WHITE)
    band_w = int(S * 0.15)
    band_top = top + h + int(h * 0.55)
    d.polygon([(cx - band_w, band_top), (cx + band_w, band_top), (cx + band_w, band_top + int(S * 0.075)),
               (cx, band_top + int(S * 0.105)), (cx - band_w, band_top + int(S * 0.075))], fill=WHITE)
    tx = cx + w - int(S * 0.02)
    d.line((tx, top + h, tx, top + h + int(S * 0.13)), fill=WHITE, width=int(S * 0.016))
    d.ellipse((tx - int(S * 0.017), top + h + int(S * 0.12), tx + int(S * 0.017), top + h + int(S * 0.155)), fill=WHITE)

    # route line with three stations
    y = int(S * 0.69)
    x0, x1 = int(S * 0.24), int(S * 0.76)
    d.rounded_rectangle((x0, y - int(S * 0.012), x1, y + int(S * 0.012)), radius=int(S * 0.012), fill=WHITE)
    r_out, r_in = int(S * 0.034), int(S * 0.018)
    for i, x in enumerate((x0, (x0 + x1) // 2, x1)):
        last = i == 2
        ro = int(r_out * (1.35 if last else 1))
        d.ellipse((x - ro, y - ro, x + ro, y + ro), fill=WHITE)
        ri = int(r_in * (1.35 if last else 1))
        d.ellipse((x - ri, y - ri, x + ri, y + ri), fill=GREEN if last else PURPLE)
    return img.resize((size, size), Image.LANCZOS)


def background(w: int, h: int, scale: int = 1) -> Image.Image:
    """DMG window background: plain ground, one purple arrow between the two icon slots, one line of text."""
    W, H = w * scale, h * scale
    img = Image.new("RGB", (W, H), (248, 248, 250))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 6 * scale), fill=PURPLE[:3])
    ay = int(H * 0.46)
    x0, x1 = int(W * 0.40), int(W * 0.60)
    d.line((x0, ay, x1 - 14 * scale, ay), fill=PURPLE[:3], width=5 * scale)
    d.polygon([(x1, ay), (x1 - 22 * scale, ay - 14 * scale), (x1 - 22 * scale, ay + 14 * scale)], fill=PURPLE[:3])
    try:
        font = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", 15 * scale)
    except OSError:
        font = ImageFont.load_default()
    msg = "Drag CAESAR Course Check to Applications"
    tw = d.textlength(msg, font=font)
    d.text(((W - tw) / 2, int(H * 0.80)), msg, fill=(92, 90, 108), font=font)
    return img


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    master = icon(1024)
    master.save(ASSETS / "icon-1024.png")
    master.resize((256, 256), Image.LANCZOS).save(ASSETS / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    background(600, 380).save(ASSETS / "dmg-bg.png")
    background(600, 380, 2).save(ASSETS / "dmg-bg@2x.png")
    if sys.platform == "darwin":
        iconset = ASSETS / "AppIcon.iconset"
        shutil.rmtree(iconset, ignore_errors=True)
        iconset.mkdir()
        for base in (16, 32, 128, 256, 512):
            master.resize((base, base), Image.LANCZOS).save(iconset / f"icon_{base}x{base}.png")
            master.resize((base * 2, base * 2), Image.LANCZOS).save(iconset / f"icon_{base}x{base}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(ASSETS / "AppIcon.icns")], check=True)
        shutil.rmtree(iconset)
        # Retina-aware DMG background (1x + 2x in one TIFF)
        subprocess.run(["tiffutil", "-cathidpicheck", str(ASSETS / "dmg-bg.png"), str(ASSETS / "dmg-bg@2x.png"),
                        "-out", str(ASSETS / "dmg-bg.tiff")], check=True, capture_output=True)
    print("wrote", sorted(p.name for p in ASSETS.iterdir()))


if __name__ == "__main__":
    main()
