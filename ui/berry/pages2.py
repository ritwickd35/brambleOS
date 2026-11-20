# Berry mock-ups v2: every element the original pages show (audit 2026-11-21), plus dialog + Level page
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
import numpy as np
from PIL import Image
from pages import C, THEMES, W, H, XX, YY, cov, sdf_rr

def poly(c, pts, col, a=1.0):
    pts = np.array(pts, float); cx, cy = pts.mean(0); d = []
    for i in range(len(pts)):
        p, q = pts[i], pts[(i + 1) % len(pts)]; e = q - p; n = np.hypot(*e); d.append(((XX - p[0]) * e[1] - (YY - p[1]) * e[0]) / n)
    ref = ((cx - pts[0][0]) * (pts[1] - pts[0])[1] - (cy - pts[0][1]) * (pts[1] - pts[0])[0]); sgn = 1 if ref > 0 else -1
    c.blend(np.clip(0.5 + np.min([sgn * x for x in d], 0), 0, 1), col, a)

def batt(c, x, y, lvl=0.8, chg=False):
    t = c.t; c.rr(x, y, 15, 8, 2.5, t["sub"], 0.85); c.rr(x + 1.5, y + 1.5, 12, 5, 1.3, t["track"]); c.rr(x + 1.5, y + 1.5, max(12 * lvl, 2.6), 5, 1.3, t["on"] if lvl > 0.25 else t["warn"])
    c.rr(x + 15, y + 2.5, 1.8, 3, 0.9, t["sub"], 0.85)
    if chg: poly(c, [(x + 8, y + 1), (x + 5, y + 4.6), (x + 7.4, y + 4.6), (x + 6.4, y + 7.5), (x + 10, y + 3.4), (x + 7.8, y + 3.4)], (255, 255, 255), 0.9)

def speaker(c, x, y, col):
    c.rr(x, y + 3, 3, 4, 0.8, col); poly(c, [(x + 3, y + 3), (x + 7, y), (x + 7, y + 10), (x + 3, y + 7)], col); c.arc(x + 8, y + 5, 3.2, 1.2, -50, 50, col); c.arc(x + 8, y + 5, 5.5, 1.2, -50, 50, col, 0.7)

def chip(c, x, y, col):
    c.rr(x + 2, y + 2, 6, 6, 1.2, col)
    for k in (3, 6): c.rr(x + k, y, 1, 2, 0.4, col); c.rr(x + k, y + 8, 1, 2, 0.4, col); c.rr(x, y + k, 2, 1, 0.4, col); c.rr(x + 8, y + k, 2, 1, 0.4, col)

def pill(c, x, y, w, h, txt, on=True, size=7, fill=None):
    t = c.t; c.rr(x, y, w, h, h / 2, fill if fill is not None else (t["ring"] if on else t["track"]))
    c.text(x + w / 2, y + h / 2, txt, size, ((30, 12, 30) if t["dark"] else (255, 250, 240)) if on and fill is None else (t["sub"] if fill is None else (255, 255, 255)), "mm")

def tabs(c, items, sel, y=104):
    t = c.t
    for i, nm in enumerate(items):
        x = 3 + i * 31; c.tile(x, y, 28, 20, i == sel, sel=(i == sel), r=5); c.text(x + 14, y + 10, nm, 7, t["text"] if i == sel else t["sub"], "mm")
    poly(c, [(3 + sel * 31 + 11, y - 4), (3 + sel * 31 + 17, y - 4), (3 + sel * 31 + 14, y - 1)], t["ring"])
    c.text(1, y + 10, "<", 7, t["sub"], "mm", 0.0)

def home(th):
    c = C(th); t = th
    pill(c, 3, 2, 24, 10, "BT", True, 7); c.disc(8, 7, 1.8, t["on"]);                          # Bluetooth on (stock: BT + switch)
    speaker(c, 31, 2, t["text"]); c.bar(43, 5, 40, 5, 1.0, t["ring"]); c.text(86, 7.5, "100", 7, t["text"], "lm")   # master volume
    c.text(112, 7.5, "G", 8, (232, 150, 60), "mm"); c.disc(123, 9, 1.7, (232, 150, 60)); c.rr(124.2, 2.5, 1.0, 7, 0.5, (232, 150, 60))   # G-EQ on, drum playing
    batt(c, 138, 2, 0.8)
    poly(c, [(3, 15), (3, 25), (8, 20)], t["ring"]); pill(c, 10, 14, 28, 13, "P08", True, 9); c.text(43, 20.5, "UKInvasion", 10, t["text"], "lm"); c.text(114, 20.5, "*", 10, t["sub"], "lm")
    kinds = ["NR", "FX1", "DRV", "AMP", "IR", "EQ", "FX2", "DLY", "RVB", "BPM"]; lit = {"DRV", "AMP", "IR", "DLY", "RVB"}
    for i, k in enumerate(kinds):
        x, y = 3 + (i % 5) * 31, 31 + (i // 5) * 35
        if k == "BPM": c.text(x + 13, y + 11, "120", 10, t["text"], "mm"); c.text(x + 13, y + 27, "BPM", 7, t["sub"], "ma"); continue
        c.tile(x, y, 26, 25, k in lit, sel=(k == "DRV")); c.sprite(k, x - 1, y + 0.5, k in lit); c.text(x + 13, y + 27, k, 7, t["text"] if k in lit else t["sub"], "ma")
    chip(c, 3, 103, t["sub"]); c.bar(16, 106, 38, 5, 0.28, t["on"]); c.text(57, 108.5, "28%", 7, t["text"], "lm")
    c.text(84, 108.5, "ENG", 7, t["sub"], "lm"); c.bar(101, 106, 36, 5, 0.77, t["warn"]); c.text(140, 108.5, "77%", 7, t["text"], "lm")
    return c.out()

def edit(th):
    c = C(th); t = th; kinds = ["NR", "FX1", "DRV", "AMP", "IR", "EQ", "FX2", "DLY", "RVB"]; lit = {"DRV", "AMP", "IR", "DLY"}
    c.text(4, 6, "P08  UKInvasion", 8, t["text"], "lm"); c.text(84, 6, "*", 8, t["sub"], "lm"); batt(c, 138, 2, 0.8)
    for i, k in enumerate(kinds): c.tile(4 + i * 17, 12, 15, 13, k in lit, sel=(k == "AMP"), r=3)
    c.tile(4, 29, 48, 40, True, r=6); c.bigamp(7, 30); c.text(58, 31, "JCM800", 11, t["text"]); c.text(58, 44, "Marshall 2203", 7, t["sub"])
    pill(c, 122, 30, 32, 12, "ON", True, 8, fill=t["on"])
    c.rr(58, 54, 64, 12, 6, t["track"]); c.rr(91, 55, 30, 10, 5, t["ring"]); c.text(74, 60, "Basic", 7, t["sub"], "mm"); c.text(106, 60, "NAM", 7, (30, 12, 30) if t["dark"] else (255, 250, 240), "mm")
    pts = [(104 + i, 49 - 4 * math.sin(i / 7.0) - 2 * math.sin(i / 3.1)) for i in range(0, 50)]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]): c.blend(cov(np.abs((YY - y0) - (y1 - y0) * (XX - x0)) - 0.8) * ((XX >= x0) & (XX <= x1 + 1)), t["ring"], 0.9)
    c.text(128, 64, "tone", 6, t["sub"], "mm")
    for k, (lab, v) in enumerate((("GAIN", 72), ("BASS", 55), ("MID", 60), ("TREB", 48))):
        cx, cy = 20 + 40 * k, 91; col = t["ring"] if k == 0 else t["sub"]
        c.arc(cx, cy, 12, 3, 0, 360, t["track"]); c.arc(cx, cy, 12, 3, 135, 135 + 2.7 * v, col)
        c.text(cx, cy, str(v), 9, t["text"] if k == 0 else t["sub"], "mm"); c.text(cx, 108, lab, 7, col, "ma")
    c.text(4, 122, "< >  block      hold  move      push  next", 6, t["sub"], "lm"); c.disc(142, 122, 1.5, t["ring"]); c.disc(148, 122, 1.5, t["sub"], 0.6)
    return c.out()

def tuner(th):
    c = C(th); t = th
    c.text(80, 6, "A4 = 440 Hz", 8, t["sub"], "ma"); c.text(80, 36, "E", 32, t["text"], "mm"); c.text(98, 26, "2", 10, t["sub"], "lm"); c.text(80, 60, "82.7 Hz", 7, t["sub"], "mm")
    for i in range(-5, 6):
        a = math.radians(-90 + i * 13); c.disc(80 + 54 * math.cos(a), 100 + 54 * math.sin(a), 2.0 if i else 2.8, t["ring"] if i == 0 else t["sub"], 0.9 if i == 0 else 0.55)
    a = math.radians(-90 + 2.2 * 13)
    for r in np.linspace(0, 48, 60): c.disc(80 + r * math.cos(a), 100 + r * math.sin(a), 1.2 if r > 6 else 2.0, t["ring"], 0.9)
    c.sheen_disc(80, 100, 5, t["ring"]); c.text(80, 74, "+4 cents", 8, t["text"], "mm")
    poly(c, [(10, 108), (10, 124), (2, 116)], t["track"] if False else t["sub"], 0.55); poly(c, [(150, 108), (150, 124), (158, 116)], t["ring"])    # flat / sharp triangles
    pill(c, 40, 108, 80, 14, "MUTE", True, 8, fill=t["warn"]); c.text(80, 125, "hold: bypass", 6, t["sub"], "mm")
    return c.out()

def recording(th):
    c = C(th); t = th
    pill(c, 5, 3, 28, 13, "P08", True, 9); c.text(38, 9.5, "UKInvasion", 9, t["text"], "lm"); chip(c, 106, 4, t["sub"]); c.text(118, 9, "27%", 8, t["text"], "lm"); batt(c, 140, 5, 0.8)
    c.tile(5, 20, 76, 44, True, r=6); c.arc(28, 42, 15, 3, 0, 360, t["track"]); c.arc(28, 42, 15, 3, 270, 330, t["warn"]); c.sheen_disc(28, 42, 8, t["warn"])
    c.text(48, 33, "0.0s", 12, t["text"], "lm"); c.text(48, 50, "Empty", 8, t["sub"], "lm")
    c.rr(86, 22, 68, 20, 10, t["track"]); c.rr(120, 24, 32, 16, 8, t["ring"]); c.text(103, 32, "Pre", 8, t["sub"], "mm"); c.text(136, 32, "Post", 8, (30, 12, 30) if t["dark"] else (255, 250, 240), "mm")
    c.text(120, 52, "Looper", 7, t["sub"], "mm")
    c.text(6, 71, "REC VOL", 8, t["text"]); c.text(78, 71, "100", 8, t["sub"], "ra"); c.bar(6, 83, 72, 6, 1.0, t["ring"])
    c.text(84, 71, "Play VOL", 8, t["text"]); c.text(154, 71, "100", 8, t["sub"], "ra"); c.bar(84, 83, 70, 6, 1.0, t["on"])
    c.tile(5, 95, 72, 26, True, sel=True); c.disc(27, 108, 6, t["warn"]); c.text(39, 108, "/", 12, t["sub"], "mm"); poly(c, [(48, 102), (48, 114), (57, 108)], t["text"])
    c.tile(83, 95, 72, 26, True); c.rr(105, 102, 12, 12, 2.5, t["text"], 0.9); c.text(129, 108, "|", 12, t["sub"], "mm"); c.text(140, 108, "x", 11, t["sub"], "mm")
    return c.out()

def drum(th):
    c = C(th); t = th
    c.text(6, 7, "Drum machine", 8, t["sub"], "lm"); batt(c, 138, 3, 0.8)
    c.tile(4, 16, 62, 52, True, r=7)
    for k in range(3): c.arc(35, 42, 17 + 3.2 * k, 2.2, 0, 360, t["ring"], 0.20 - 0.05 * k)
    c.arc(35, 42, 16, 4, 0, 360, t["track"]); c.arc(35, 42, 16, 4, 270, 380, t["ring"]); c.sheen_disc(35, 42, 11, t["tile_off"]); poly(c, [(31, 36), (31, 48), (41, 42)], t["text"])
    c.text(72, 22, "Type", 7, t["sub"]); c.text(152, 22, "Rock 1", 9, t["text"], "ra")
    c.text(72, 36, "VOL", 7, t["sub"]); c.bar(92, 38, 62, 5, 0.7, t["ring"])
    c.text(152, 54, "120", 20, t["text"], "ra"); c.text(72, 52, "BPM", 7, t["sub"])
    names = ("Play/Stop", "Type", "VOL", "BPM")
    for i, nm in enumerate(names):
        x = 3 + i * 39; c.tile(x, 76, 36, 28, True if i == 0 else False, sel=(i == 0), r=6); cx, cy = x + 18, 90
        col = t["text"] if i == 0 else t["sub"]
        if i == 0: poly(c, [(cx - 8, cy - 5), (cx - 8, cy + 5), (cx - 1, cy)], col); c.rr(cx + 2, cy - 4, 8, 8, 1.5, col)
        elif i == 1: [c.rr(cx - 7, cy - 6 + 5 * k, 14, 2.2, 1.1, col) for k in range(3)]
        elif i == 2: speaker(c, cx - 7, cy - 5, col)
        else: poly(c, [(cx - 6, cy + 6), (cx - 3, cy - 6), (cx + 3, cy - 6), (cx + 6, cy + 6)], col, 0.9); c.rr(cx - 0.6, cy - 5, 1.2, 9, 0.6, t["track"]); c.disc(cx + 2.5, cy - 1.5, 1.4, (255, 255, 255), 0.8)
        c.text(x + 18, 112, nm, 7, col, "ma")
    return c.out()

def settings(th, page="Display"):
    c = C(th); t = th
    c.arc(9, 8, 4, 1.6, 0, 360, t["sub"]); c.disc(9, 8, 1.2, t["sub"]); c.text(18, 8, page, 10, t["text"], "lm"); c.text(120, 8, "1/2", 7, t["sub"], "mm"); batt(c, 138, 3, 0.8)
    if page == "Display":
        for i, (lab, val) in enumerate((("Theme", "Mulberry"), ("Brightness", ""), ("ECO", "Off"), ("Animations", "On"))):
            y = 19 + i * 17; sel = i == 0; c.tile(4, y, 152, 15, sel, sel=sel, r=6); c.text(12, y + 7.5, lab, 8, t["text"], "lm")
            if lab == "Theme": c.text(148, y + 7.5, "<  " + val + "  >", 8, t["text"], "rm")
            elif lab == "Brightness": c.bar(84, y + 5, 54, 5, 0.85, t["ring"]); c.text(150, y + 7.5, "85", 7, t["sub"], "rm")
            else: c.rr(124, y + 2.5, 28, 10, 5, t["on"] if val == "On" else t["track"]); c.disc(146 if val == "On" else 130, y + 7.5, 3.6, (255, 255, 255) if t["dark"] or val == "On" else t["sub"])
        for i, col in enumerate(((120, 50, 110), (80, 40, 120), (170, 40, 70), (40, 50, 110), (100, 50, 170), (245, 225, 195))):
            c.disc(18 + 25 * i, 94, 5.5, col); c.disc(16.5 + 25 * i, 92.5, 1.8, (255, 255, 255), 0.35)
            if i == 0: c.arc(18, 94, 8, 1.4, 0, 360, t["ring"])
    tabs(c, ["USB", "Boot", "Display", "BT", "MIDI"] if page == "Display" else ["Level", "G-EQ", "USB", "Boot", "Display"], 2 if page == "Display" else 0)
    return c.out()

def level(th):
    c = C(th); t = th
    c.arc(9, 8, 4, 1.6, 0, 360, t["sub"]); c.disc(9, 8, 1.2, t["sub"]); c.text(18, 8, "Level", 10, t["text"], "lm"); batt(c, 138, 3, 0.8)
    c.tile(4, 19, 152, 40, True, sel=True, r=7); c.text(12, 30, "Input Level", 8, t["text"], "lm"); c.text(148, 30, "0 dB", 8, t["text"], "rm")
    c.bar(12, 42, 136, 8, 0.0, t["on"]); c.rr(12, 42, 136, 8, 4, t["track"])
    for x0, x1, col in ((12, 92, t["on"]), (92, 124, (225, 180, 60)), (124, 148, t["warn"])):
        m = cov(sdf_rr(12, 42, 136, 8, 4)) * ((XX >= x0) & (XX < x1)) * (XX < 100); c.blend(m, col)
    c.rr(103, 40, 2, 12, 1, (255, 255, 255), 0.9)
    c.text(80, 70, "play hard: aim for the amber zone", 7, t["sub"], "mm")
    tabs(c, ["Level", "G-EQ", "USB", "Boot", "Display"], 0)
    return c.out()

def dialog(th):
    c = C(th); t = th; base = home(th).astype(float); c.im = base * 0.35 + np.array(t["bg"][1], float) * 0.1 if t["dark"] else base * 0.55 + 80
    c.tile(14, 28, 132, 72, True, r=9); c.text(80, 42, "Save changes?", 10, t["text"], "mm"); c.text(80, 56, "P08  UKInvasion", 8, t["sub"], "mm")
    pill(c, 26, 72, 52, 18, "Save", True, 9, fill=t["on"]); pill(c, 82, 72, 52, 18, "Discard", False, 9); c.arc(52, 81, 0.01, 0.1, 0, 1, t["ring"], 0)
    c.blend(cov(sdf_rr(26, 72, 52, 18, 9) - 2.5) * (1 - cov(sdf_rr(26, 72, 52, 18, 9) - 0.5)), t["ring"], 0.6)
    return c.out()

PAGES = (("Home", home), ("Edit", edit), ("Tuner", tuner), ("Recording", recording), ("Drums", drum), ("Settings", settings), ("Level", level), ("Dialog", dialog))
if __name__ == "__main__":
    os.makedirs("ui/berry/pages", exist_ok=True)
    for tn, th in THEMES.items():
        sheet = Image.new("RGB", (4 * (W * 3 + 10) + 10, 2 * (H * 3 + 10) + 10), (12, 12, 14))
        for i, (pn, fn) in enumerate(PAGES):
            img = Image.fromarray(fn(th)); img.save(f"ui/berry/pages/{tn}_{pn}.png")
            sheet.paste(img.resize((W * 3, H * 3), Image.NEAREST), (10 + (i % 4) * (W * 3 + 10), 10 + (i // 4) * (H * 3 + 10)))
        sheet.save(f"ui/berry/pages/sheet2_{tn}.png"); print(tn, "ok")
