#!/usr/bin/env python3
"""Real-size mock-ups of the new home and edit screens (160 x 128, RGB565-safe colours), plus 4x previews.
  ui_mock.py -> ui/mock_home.png, ui/mock_edit.png (+ _4x)"""
import os
from PIL import Image, ImageDraw, ImageFont
RE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(RE, "ui")
W, H = 160, 128
F = ImageFont.load_default()
BG0, BG1 = (10, 12, 20), (24, 28, 44)


def bg():
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    for y in range(H):                                            # vertical gradient + vignette
        t = y / H; d.line([(0, y), (W, y)], fill=tuple(int(BG1[i] * (1 - t) + BG0[i] * t) for i in range(3)))
    return im, d


def tiny(d, xy, s, fill):                                        # 5x7-ish label text (default font)
    d.text(xy, s, font=F, fill=fill)


# --- miniature gear sprites (28 x 24) -------------------------------------------------------------
def pedal(d, x, y, body, knob=(230, 230, 230), on=True):
    c = body if on else (60, 60, 60)
    d.rounded_rectangle([x + 4, y + 1, x + 23, y + 23], 3, fill=c, outline=(0, 0, 0))
    for kx in (x + 8, x + 13, x + 18): d.ellipse([kx - 2, y + 4, kx + 2, y + 8], fill=knob if on else (90, 90, 90))
    d.rectangle([x + 9, y + 13, x + 18, y + 16], fill=(250, 250, 250) if on else (80, 80, 80))
    d.ellipse([x + 11, y + 18, x + 16, y + 22], fill=(170, 170, 170) if on else (70, 70, 70))


def amphead(d, x, y, on=True):
    d.rounded_rectangle([x + 1, y + 4, x + 26, y + 21], 2, fill=(20, 20, 20) if on else (45, 45, 45), outline=(120, 120, 120))
    d.rectangle([x + 3, y + 6, x + 24, y + 11], fill=(200, 160, 60) if on else (80, 70, 50))
    for k in range(6): d.point((x + 5 + 3 * k, y + 8), fill=(30, 30, 30))
    d.rectangle([x + 3, y + 13, x + 24, y + 19], fill=(60, 50, 40) if on else (50, 50, 50))


def cab(d, x, y, on=True):
    d.rectangle([x + 3, y + 1, x + 24, y + 23], fill=(30, 30, 30) if on else (45, 45, 45), outline=(140, 140, 140))
    g = (110, 100, 80) if on else (60, 60, 60)
    for yy in range(y + 3, y + 22, 2): d.line([(x + 5, yy), (x + 22, yy)], fill=g)
    for cx, cy in ((x + 9, y + 7), (x + 18, y + 7), (x + 9, y + 17), (x + 18, y + 17)): d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], outline=(160, 150, 120) if on else (70, 70, 70))


def eq(d, x, y, on=True):
    d.rounded_rectangle([x + 2, y + 2, x + 25, y + 22], 2, fill=(40, 40, 48) if on else (45, 45, 45), outline=(150, 150, 160))
    for k, h in enumerate((8, 14, 6, 11, 16)):
        xx = x + 6 + 4 * k; d.line([(xx, y + 5), (xx, y + 19)], fill=(90, 90, 100)); d.rectangle([xx - 1, y + 5 + h // 2, xx + 1, y + 7 + h // 2], fill=(240, 90, 160) if on else (90, 90, 90))


def gate(d, x, y, on=True):
    pedal(d, x, y, (40, 80, 160), on=on)


SPR = {"NR": lambda d, x, y, on: gate(d, x, y, on), "FX1": lambda d, x, y, on: pedal(d, x, y, (40, 170, 90), on=on),
       "DRV": lambda d, x, y, on: pedal(d, x, y, (40, 160, 70), on=on), "AMP": lambda d, x, y, on: amphead(d, x, y, on),
       "IR": lambda d, x, y, on: cab(d, x, y, on), "EQ": lambda d, x, y, on: eq(d, x, y, on),
       "FX2": lambda d, x, y, on: pedal(d, x, y, (230, 140, 40), on=on), "DLY": lambda d, x, y, on: pedal(d, x, y, (60, 120, 220), on=on),
       "RVB": lambda d, x, y, on: pedal(d, x, y, (150, 80, 210), on=on)}
ACC = {"NR": (90, 140, 255), "FX1": (90, 220, 120), "DRV": (255, 90, 80), "AMP": (255, 170, 60), "IR": (255, 220, 70),
       "EQ": (255, 110, 190), "FX2": (255, 150, 60), "DLY": (100, 170, 255), "RVB": (190, 120, 255)}


def home(on):
    im, d = bg()
    d.rounded_rectangle([3, 2, 27, 15], 3, fill=(255, 190, 40)); tiny(d, (6, 3), "P08", (20, 20, 20))
    tiny(d, (32, 3), "UKInvasion*", (240, 240, 250)); d.rectangle([140, 5, 155, 11], outline=(200, 200, 200)); d.rectangle([142, 7, 151, 9], fill=(120, 230, 120))
    order = ["NR", "FX1", "DRV", "AMP", "IR", "EQ", "FX2", "DLY", "RVB", "BPM"]
    for i, nm in enumerate(order):
        cx = 2 + (i % 5) * 32; cy = 19 + (i // 5) * 51
        if i % 5 < 4 and nm != "BPM": d.line([(cx + 27, cy + 13), (cx + 33, cy + 13)], fill=(70, 80, 110), width=1)   # cable
        if nm == "BPM":
            tiny(d, (cx + 4, cy + 6), "120", (230, 230, 230)); tiny(d, (cx + 6, cy + 30), "BPM", (150, 150, 170)); continue
        lit = on.get(nm, False)
        if lit: d.rounded_rectangle([cx - 1, cy - 1, cx + 29, cy + 25], 4, outline=tuple(int(c * 0.6) for c in ACC[nm]))     # glow
        SPR[nm](d, cx, cy, lit)
        tiny(d, (cx + 14 - 3 * len(nm), cy + 28), nm, ACC[nm] if lit else (90, 90, 100))
    for k, (lab, v, x0) in enumerate((("DSP", 0.48, 3), ("ENG", 0.77, 82))):
        tiny(d, (x0, 117), lab, (150, 150, 170)); x1 = x0 + 20; d.rectangle([x1, 121, x1 + 55, 124], fill=(40, 40, 55))
        d.rectangle([x1, 121, x1 + int(55 * v), 124], fill=(90, 220, 120) if v < 0.7 else (250, 190, 60))
    return im


def edit():
    im, d = bg()
    order = ["NR", "FX1", "DRV", "AMP", "IR", "EQ", "FX2", "DLY", "RVB"]; on = {"DRV": 1, "AMP": 1, "IR": 1, "DLY": 1}
    for i, nm in enumerate(order):
        x = 3 + i * 17; c = ACC[nm] if nm in on else (60, 60, 70)
        d.rounded_rectangle([x, 2, x + 14, 14], 2, fill=tuple(int(v * 0.35) for v in c), outline=c)
        if nm == "AMP": d.rounded_rectangle([x - 1, 1, x + 15, 15], 2, outline=(255, 255, 255))
    d.line([(0, 18), (W, 18)], fill=(60, 60, 80))
    im2 = Image.new("RGB", (28, 24)); dd = ImageDraw.Draw(im2); dd.rectangle([0, 0, 28, 24], fill=BG1); amphead(dd, 0, 0)
    im.paste(im2.resize((42, 36), Image.NEAREST), (3, 22))
    tiny(d, (50, 21), "JCM800", (255, 190, 80)); tiny(d, (50, 31), "Marshall 2203", (150, 150, 170))
    d.rounded_rectangle([132, 21, 156, 31], 3, fill=(60, 180, 90)); tiny(d, (136, 21), "ON", (10, 30, 10))
    pts = [(50 + i, 56 - int(7 * __import__("math").sin(i / 9.0) + 3 * __import__("math").sin(i / 3.5))) for i in range(104)]
    d.line(pts, fill=(255, 170, 60), width=1); tiny(d, (50, 59), "bass  mid  treble", (110, 110, 130))
    d.line([(0, 72), (W, 72)], fill=(60, 60, 80))
    for k, (lab, v) in enumerate((("GAIN", 72), ("BASS", 55), ("MID", 60), ("TREB", 48))):
        cx = 20 + k * 40; cy = 92; sel = k == 0; col = (255, 190, 80) if sel else (170, 170, 190)
        d.arc([cx - 13, cy - 13, cx + 13, cy + 13], 135, 405, fill=(60, 60, 80), width=3)
        d.arc([cx - 13, cy - 13, cx + 13, cy + 13], 135, 135 + int(270 * v / 100), fill=col, width=3)
        tiny(d, (cx - 7, cy - 5), str(v), col); tiny(d, (cx - 3 * len(lab), 108), lab, col)
    d.ellipse([140, 120, 143, 123], fill=(220, 220, 220)); d.ellipse([147, 120, 150, 123], fill=(80, 80, 90))
    return im


def main():
    for n, im in (("home", home({"DRV": 1, "AMP": 1, "IR": 1, "DLY": 1, "RVB": 1})), ("edit", edit())):
        im.save(os.path.join(OUT, f"mock_{n}.png")); im.resize((W * 4, H * 4), Image.NEAREST).save(os.path.join(OUT, f"mock_{n}_4x.png"))
    print("ui/mock_home(_4x).png, ui/mock_edit(_4x).png")


if __name__ == "__main__":
    main()
