# Berry UI mock-ups (soft style): home, edit, tuner, recording, drum, settings; Mulberry (dark) + Cloudberry (light)
import numpy as np, math
from PIL import Image, ImageDraw, ImageFont
W, H = 160, 128
THEMES = {
 "Mulberry":   dict(dark=True,  bg=((46, 16, 44), (18, 6, 20)), tile=(60, 30, 64), tile_off=(36, 18, 40), text=(238, 224, 242), sub=(170, 140, 180), hi=(176, 120, 190), ring=(214, 160, 232), on=(120, 200, 120), warn=(210, 52, 84), dim=0.45, track=(14, 6, 16)),
 "Cloudberry": dict(dark=False, bg=((252, 244, 230), (238, 222, 205)), tile=(255, 252, 244), tile_off=(232, 220, 206), text=(70, 38, 60), sub=(140, 110, 130), hi=(255, 255, 255), ring=(224, 150, 70), on=(80, 160, 90), warn=(200, 60, 80), dim=0.55, track=(222, 206, 192)),
}
def q565(a):
    a = a.astype(float); r = np.round(a[..., 0] / 255 * 31) * 255 / 31; g = np.round(a[..., 1] / 255 * 63) * 255 / 63; b = np.round(a[..., 2] / 255 * 31) * 255 / 31
    return np.stack([r, g, b], -1).clip(0, 255).astype(np.uint8)
YY, XX = np.mgrid[0:H, 0:W] + 0.5
cov = lambda d: np.clip(0.5 - d, 0, 1)
def sdf_rr(x, y, w, h, r):
    qx = np.abs(XX - (x + w / 2)) - (w / 2 - r); qy = np.abs(YY - (y + h / 2)) - (h / 2 - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r

class C:
    def __init__(s, th):
        s.t = th; top, bot = np.array(th["bg"][0], float), np.array(th["bg"][1], float)
        t = np.linspace(0, 1, H)[:, None, None]; s.im = (top * (1 - t) + bot * t) * np.ones((1, W, 1))
        bay = np.array([[0, 2], [3, 1]]) / 4 - 0.375; s.im += np.tile(bay, (H // 2, W // 2))[..., None] * (255 / 31)
        s.fonts = {}
    def blend(s, m, col, a=1.0):
        k = (np.clip(m, 0, 1) * a)[..., None]; s.im = s.im * (1 - k) + np.broadcast_to(np.asarray(col, float), s.im.shape) * k
    def rr(s, x, y, w, h, r, col, a=1.0): s.blend(cov(sdf_rr(x, y, w, h, r)), col, a)
    def disc(s, cx, cy, r, col, a=1.0): s.blend(cov(np.hypot(XX - cx, YY - cy) - r), col, a)
    def arc(s, cx, cy, r, th, a0, a1, col, a=1.0):                     # ring segment, angles in degrees (0 = right, clockwise)
        d = np.hypot(XX - cx, YY - cy); ang = (np.degrees(np.arctan2(YY - cy, XX - cx)) + 360) % 360
        a0, a1 = a0 % 360, a1 % 360; inside = (ang >= a0) & (ang <= a1) if a0 <= a1 else (ang >= a0) | (ang <= a1)
        s.blend(cov(np.abs(d - r) - th / 2) * inside, col, a)
    def font(s, size):
        if size not in s.fonts: s.fonts[size] = ImageFont.load_default(size=size)
        return s.fonts[size]
    def text(s, x, y, txt, size=9, col=None, anchor="la", a=1.0):
        m = Image.new("L", (W, H), 0); ImageDraw.Draw(m).text((x, y), txt, font=s.font(size), fill=255, anchor=anchor)
        s.blend(np.asarray(m, float) / 255, col if col is not None else s.t["text"], a)
    def tile(s, x, y, w, h, lit=True, sel=False, r=5):
        t = s.t; full = sdf_rr(x, y, w, h, r); base = np.array(t["tile"] if lit else t["tile_off"], float)
        if sel: s.blend(cov(full - 2.5) * (1 - cov(full - 0.5)), t["ring"], 0.30); s.blend(cov(full - 1.5) * (1 - cov(full - 0.5)), t["ring"], 0.6)
        s.blend(cov(sdf_rr(x, y + 1.5, w, h, r) - 0.5), (0, 0, 0) if t["dark"] else (120, 90, 80), 0.28 if t["dark"] else 0.14)
        g = np.clip((YY - y) / h, 0, 1)[..., None]; s.blend(cov(full), base * (1.07 - 0.14 * g))
        inner = np.clip(1 - (-full) / 2.2, 0, 1) * cov(full + 0.2); dirk = np.clip(1 - ((XX - x) / w + (YY - y) / h) * 0.9, 0, 1)
        s.blend(inner * dirk, t["hi"], 0.30 if t["dark"] else 0.9)
        s.blend(np.clip(1 - (-full) / 2.0, 0, 1) * cov(full + 0.2) * (1 - dirk), (0, 0, 0) if t["dark"] else (150, 110, 100), 0.18)
    def bar(s, x, y, w, h, v, col):
        s.blend(cov(sdf_rr(x, y, w, h, h / 2)), s.t["track"], 1.0)
        if v > 0: s.blend(cov(sdf_rr(x, y, max(w * v, h), h, h / 2)), col)
        s.blend(cov(sdf_rr(x, y, max(w * v, h), h, h / 2)) * np.clip(1 - (YY - y) / (h * 0.6), 0, 1) , (255, 255, 255), 0.22)
    def sheen_disc(s, cx, cy, r, col, a=1.0):
        s.disc(cx, cy, r, col, a); s.disc(cx - r * 0.3, cy - r * 0.35, r * 0.4, (255, 255, 255), 0.35 * a)
    # ---- gear sprites (28x24 region at x, y) ----
    def lite(s, col, lit): c = np.array(col, float); return c if lit else (c * s.t["dim"] if s.t["dark"] else c * 0.5 + 125)
    def pedal(s, x, y, body, lit=True, big=1.0):
        b = s.lite(body, lit); bx, by, bw, bh = x + 6, y + 2, 16, 20
        m = sdf_rr(bx, by, bw, bh, 3); g = np.clip((YY - by) / bh, 0, 1)[..., None]
        s.blend(cov(m), b * (1.18 - 0.36 * g)); s.blend(np.clip(1 - (-m) / 1.6, 0, 1) * cov(m + 0.2) * 0.5, (255, 255, 255), 0.30 if lit else 0.12)
        s.blend(np.clip(1 - (-m) / 1.6, 0, 1) * cov(m + 0.2) * np.clip((YY - (by + 11)) / 9, 0, 1), (0, 0, 0), 0.28)
        for kx in (3, 8, 13): s.sheen_disc(bx + kx, by + 4.2, 2.0, (235, 232, 226) if lit else (170, 165, 165))
        s.rr(bx + 3, by + 9, 10, 4, 1.5, (250, 248, 240) if lit else (190, 185, 185)); s.sheen_disc(bx + 8, by + 17, 2.4, (165, 165, 172) if lit else (130, 130, 135))
    def amp(s, x, y, lit=True):
        b = s.lite((205, 160, 70), lit); s.rr(x + 3, y + 5, 22, 15, 2.5, (30, 24, 26) if lit else (72, 64, 66)); s.rr(x + 4, y + 6, 20, 6, 1.5, b)
        for k in range(5): s.disc(x + 7 + 3.2 * k, y + 9, 0.8, (40, 30, 20)); 
        s.rr(x + 4, y + 13, 20, 6, 1.5, (60, 48, 44) if lit else (92, 82, 80))
    def cab(s, x, y, lit=True):
        s.rr(x + 4, y + 2, 20, 20, 2.5, (32, 28, 30) if lit else (72, 64, 66)); g = (120, 105, 85) if lit else (95, 88, 84)
        for k in range(5): s.rr(x + 6, y + 5 + 3 * k, 16, 1.2, 0.6, g, 0.8)
        s.sheen_disc(x + 14, y + 12, 5, (60, 52, 50) if lit else (88, 80, 78), 0.8)
    def eqs(s, x, y, lit=True):
        s.rr(x + 3, y + 3, 22, 18, 3, (50, 46, 62) if lit else (86, 82, 96))
        for k, h in enumerate((6, 11, 4, 9, 7)): s.rr(x + 6 + 3.6 * k, y + 5, 1.2, 14, 0.6, (24, 20, 30) if lit else (60, 56, 70)); s.rr(x + 5 + 3.6 * k, y + 16 - h, 3.2, 2.4, 1.0, (232, 100, 170) if lit else (150, 110, 140))
    def sprite(s, kind, x, y, lit=True):
        {"NR": lambda: s.pedal(x, y, (50, 100, 190), lit), "FX1": lambda: s.pedal(x, y, (40, 160, 90), lit), "DRV": lambda: s.pedal(x, y, (210, 70, 70), lit),
         "AMP": lambda: s.amp(x, y, lit), "IR": lambda: s.cab(x, y, lit), "EQ": lambda: s.eqs(x, y, lit), "FX2": lambda: s.pedal(x, y, (230, 140, 50), lit),
         "DLY": lambda: s.pedal(x, y, (60, 130, 230), lit), "RVB": lambda: s.pedal(x, y, (150, 90, 215), lit)}[kind]()
    def bigamp(s, x, y, lit=True):      # ~42x36 with a real gradient on the face
        s.rr(x, y + 4, 42, 30, 4, (28, 22, 24)); g = np.clip((YY - (y + 6)) / 12, 0, 1)[..., None]
        s.blend(cov(sdf_rr(x + 2, y + 6, 38, 12, 2.5)), np.array((215, 170, 80)) * (1.15 - 0.3 * g)); s.rr(x + 2, y + 21, 38, 11, 2.5, (62, 50, 46))
        for k in range(6): s.sheen_disc(x + 8 + 5.4 * k, y + 12, 1.6, (40, 30, 20))
        s.rr(x + 2, y + 6, 38, 1.3, 0.6, (255, 240, 200), 0.5)
    def out(s): return q565(s.im)

def label(c, x, y, w, txt): c.text(x + w / 2, y, txt, 7, c.t["text"], "ma")

def home(th):
    c = C(th); t = th
    c.rr(6, 5, 30, 14, 7, t["ring"]); c.text(21, 12, "P08", 9, (30, 12, 30) if t["dark"] else (255, 250, 240), "mm"); c.text(42, 12, "UKInvasion", 10, t["text"], "lm"); c.text(110, 13, "*", 10, t["sub"], "lm")
    c.rr(139, 8, 15, 8, 2.5, t["sub"], 0.9); c.rr(141, 10, 9, 4, 1, t["on"])
    kinds = ["NR", "FX1", "DRV", "AMP", "IR", "EQ", "FX2", "DLY", "RVB"]; lit = {"DRV", "AMP", "IR", "DLY", "RVB"}
    for i, k in enumerate(kinds + ["BPM"]):
        x, y = 4 + (i % 5) * 31, 24 + (i // 5) * 36
        if k == "BPM": c.text(x + 13, y + 9, "120", 10, t["text"], "mm"); c.text(x + 13, y + 29, "BPM", 7, t["sub"], "ma"); continue
        c.tile(x, y, 27, 27, k in lit, sel=(k == "DRV")); c.sprite(k, x - 0.5, y + 1.5, k in lit); c.text(x + 13.5, y + 29, k, 7, t["text"] if k in lit else t["sub"], "ma")
    for x0, v, col, lab in ((6, 0.45, t["on"], "DSP"), (84, 0.78, t["warn"], "ENG")):
        c.text(x0, 101, lab, 7, t["sub"]); c.bar(x0 + 17, 103, 52, 6, v, col)
    return c.out()

def edit(th):
    c = C(th); t = th; kinds = ["NR", "FX1", "DRV", "AMP", "IR", "EQ", "FX2", "DLY", "RVB"]; lit = {"DRV", "AMP", "IR", "DLY"}
    for i, k in enumerate(kinds):
        x = 4 + i * 17; c.tile(x, 3, 15, 13, k in lit, sel=(k == "AMP"), r=3)
    c.tile(4, 22, 48, 44, True, r=6); c.bigamp(7, 25); c.text(58, 24, "JCM800", 11, t["text"]); c.text(58, 38, "Marshall 2203", 7, t["sub"])
    c.rr(124, 23, 30, 13, 6.5, t["on"]); c.text(139, 30, "ON", 8, (255, 255, 255), "mm")
    pts = [(58 + i, 52 - 5 * math.sin(i / 8.0) - 2.5 * math.sin(i / 3.3)) for i in range(0, 96)]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]): c.blend(cov(np.abs((YY - y0) - (y1 - y0) * (XX - x0)) - 0.9) * ((XX >= x0) & (XX <= x1 + 1)), t["ring"], 0.9)
    c.text(58, 64, "bass      mid      treble", 6, t["sub"])
    for k, (lab, v) in enumerate((("GAIN", 72), ("BASS", 55), ("MID", 60), ("TREB", 48))):
        cx, cy = 20 + 40 * k, 92; col = t["ring"] if k == 0 else t["sub"]
        c.arc(cx, cy, 13, 3, 0, 360, t["track"]); c.arc(cx, cy, 13, 3, 135, 135 + 2.7 * v, col)
        c.text(cx, cy, str(v), 9, t["text"] if k == 0 else t["sub"], "mm"); c.text(cx, 110, lab, 7, col, "ma")
    c.disc(142, 123, 1.5, t["ring"]); c.disc(148, 123, 1.5, t["sub"], 0.6)
    return c.out()

def tuner(th):
    c = C(th); t = th
    c.text(80, 6, "A4 = 440 Hz", 8, t["sub"], "ma"); c.text(80, 38, "E", 34, t["text"], "mm"); c.text(98, 28, "2", 10, t["sub"], "lm")
    for i in range(-5, 6):
        a = math.radians(-90 + i * 13); x0, y0 = 80 + 54 * math.cos(a), 98 + 54 * math.sin(a)
        c.disc(x0, y0, 2.0 if i else 2.8, t["ring"] if i == 0 else t["sub"], 0.9 if i == 0 else 0.55)
    a = math.radians(-90 + 2.2 * 13)
    for r in np.linspace(0, 48, 60): c.disc(80 + r * math.cos(a), 98 + r * math.sin(a), 1.2 if r > 6 else 2.0, t["on"] if abs(2.2) < 1 else t["ring"], 0.9)
    c.sheen_disc(80, 98, 5, t["ring"]); c.text(80, 70, "+4 cents", 8, t["text"], "mm")
    c.rr(6, 108, 42, 15, 7, t["tile"]); c.text(27, 115, "FLAT", 8, t["sub"], "mm"); c.rr(112, 108, 42, 15, 7, t["ring"]); c.text(133, 115, "SHARP", 8, (30, 12, 30) if t["dark"] else (255, 250, 240), "mm")
    c.rr(58, 108, 44, 15, 7.5, t["warn"], 0.9); c.text(80, 115, "MUTE", 8, (255, 255, 255), "mm")
    return c.out()

def recording(th):
    c = C(th); t = th
    c.rr(6, 5, 30, 14, 7, t["ring"]); c.text(21, 12, "REC", 9, (30, 12, 30) if t["dark"] else (255, 250, 240), "mm"); c.text(42, 12, "UKInvasion", 9, t["text"], "lm"); c.text(120, 12, "27%", 8, t["sub"], "lm")
    c.tile(6, 24, 74, 44, True, r=6); c.arc(30, 46, 15, 3, 0, 360, t["track"]); c.arc(30, 46, 15, 3, 270, 330, t["warn"]); c.sheen_disc(30, 46, 8, t["warn"])
    c.text(50, 36, "0:08", 12, t["text"], "lm"); c.text(50, 53, "Empty", 8, t["sub"], "lm")
    c.rr(86, 24, 68, 20, 10, t["track"]); c.rr(121, 26, 31, 16, 8, t["ring"]); c.text(103, 34, "Pre", 8, t["sub"], "mm"); c.text(137, 34, "Post", 8, (30, 12, 30) if t["dark"] else (255, 250, 240), "mm")
    c.text(86, 50, "Looper", 7, t["sub"])
    c.text(6, 74, "REC VOL", 8, t["text"]); c.text(78, 74, "100", 8, t["sub"], "ra"); c.bar(6, 86, 70, 6, 1.0, t["ring"])
    c.text(84, 74, "Play VOL", 8, t["text"]); c.text(154, 74, "100", 8, t["sub"], "ra"); c.bar(84, 86, 70, 6, 1.0, t["on"])
    c.tile(6, 98, 72, 24, True, sel=True); c.disc(30, 110, 6, t["warn"]); c.text(40, 110, "/", 12, t["sub"], "mm"); c.text(52, 110, ">", 12, t["text"], "mm")
    c.tile(84, 98, 70, 24, True); c.rr(105, 104, 12, 12, 2.5, None or t["text"], 0.9); c.text(131, 110, "x", 12, t["sub"], "mm")
    return c.out()

def drum(th):
    c = C(th); t = th
    c.text(8, 7, "DRUMS", 8, t["sub"]); c.text(152, 7, "Rock 1", 9, t["text"], "ra")
    for k, a_ in enumerate((0.9, 0.5, 0.25)): c.arc(52, 52, 26 + 4 * k, 2.2 - k * 0.4, 0, 360, t["ring"], 0.20 * a_ * 2)
    c.arc(52, 52, 24, 4, 0, 360, t["track"]); c.arc(52, 52, 24, 4, 270, 380, t["ring"]); c.sheen_disc(52, 52, 16, t["tile"]); 
    c.text(52, 52, ">", 16, t["text"], "mm")
    c.text(150, 30, "120", 24, t["text"], "ra"); c.text(150, 58, "BPM", 8, t["sub"], "ra")
    c.text(88, 76, "Drum VOL", 8, t["text"]); c.bar(88, 88, 66, 6, 0.7, t["ring"])
    for i in range(4): c.tile(8 + 22 * i + 0, 104, 18, 16, i == 1, sel=(i == 1), r=4); c.text(17 + 22 * i, 112, "1234"[i], 8, t["text"] if i == 1 else t["sub"], "mm")
    c.text(150, 112, "Play/Stop", 7, t["sub"], "rm")
    return c.out()

def settings(th):
    c = C(th); t = th
    c.text(8, 6, "Display", 11, t["text"]); c.text(152, 8, "1/8", 7, t["sub"], "ra")
    for i, (lab, val) in enumerate((("Theme", "Mulberry"), ("Brightness", ""), ("ECO", "Off"), ("Animations", "On"))):
        y = 24 + i * 19; sel = i == 0; c.tile(4, y, 152, 17, sel, sel=sel, r=6); c.text(12, y + 8.5, lab, 8, t["text"], "lm")
        if lab == "Theme": c.text(142, y + 8.5, "<  " + val + "  >", 8, t["text"], "rm")
        elif lab == "Brightness": c.bar(84, y + 6, 54, 5, 0.85, t["ring"]); c.text(146, y + 8.5, "85", 7, t["sub"], "rm")
        else:
            c.rr(122, y + 3, 28, 11, 5.5, t["on"] if val == "On" else t["track"]); c.disc(144 if val == "On" else 128, y + 8.5, 4, (255, 255, 255) if t["dark"] or val == "On" else t["sub"])
    c.tile(4, 104, 152, 20, True, r=6)
    for i, nm in enumerate(("Mulberry", "Elder", "Lingon", "Black", "Jamun", "Cloud")):
        col = [(120, 50, 110), (80, 40, 120), (170, 40, 70), (40, 50, 110), (100, 50, 170), (245, 225, 195)][i]; c.disc(18 + 25 * i, 114, 6, col); c.disc(18 + 25 * i - 1.8, 112, 2, (255, 255, 255), 0.35)
        if i == 0: c.arc(18, 114, 8.5, 1.5, 0, 360, t["ring"])
    return c.out()

PAGES = (("Home", home), ("Edit", edit), ("Tuner", tuner), ("Recording", recording), ("Drums", drum), ("Settings", settings))
if __name__ == "__main__":
    import os; os.makedirs("ui/berry/pages", exist_ok=True)
    for tn, th in THEMES.items():
        sheet = Image.new("RGB", (3 * (W * 3 + 10) + 10, 2 * (H * 3 + 10) + 10), (12, 12, 14))
        for i, (pn, fn) in enumerate(PAGES):
            img = Image.fromarray(fn(th)); img.save(f"ui/berry/pages/{tn}_{pn}.png")
            sheet.paste(img.resize((W * 3, H * 3), Image.NEAREST), (10 + (i % 3) * (W * 3 + 10), 10 + (i // 3) * (H * 3 + 10)))
        sheet.save(f"ui/berry/pages/sheet_{tn}.png"); print(tn, "ok")
