# Berry style v2: soft edges (anti-aliased shapes), Mulberry (dark) vs Cloudberry (light), real size, RGB565-quantised
import numpy as np
from PIL import Image, ImageDraw, ImageFont
W, H = 160, 128
def q565(a):
    a = a.astype(float); r = np.round(a[..., 0] / 255 * 31) * 255 / 31; g = np.round(a[..., 1] / 255 * 63) * 255 / 63; b = np.round(a[..., 2] / 255 * 31) * 255 / 31
    return np.stack([r, g, b], -1).clip(0, 255).astype(np.uint8)
def sdf_rr(w, h, r, ox=0.0, oy=0.0, W_=None, H_=None):          # signed distance to a rounded rect (negative inside), pixel centres
    W_ = W_ or w; H_ = H_ or h
    yy, xx = np.mgrid[0:H_, 0:W_] + 0.5
    px = xx - (ox + w / 2); py = yy - (oy + h / 2); qx = np.abs(px) - (w / 2 - r); qy = np.abs(py) - (h / 2 - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r
cov = lambda d: np.clip(0.5 - d, 0, 1)                          # anti-aliased coverage from a distance
def blend(img, m, col, a=1.0):
    col = np.broadcast_to(np.asarray(col, float), img.shape); k = (m * a)[..., None]; img[:] = img * (1 - k) + col * k
def disc(img, cx, cy, r, col, a=1.0):
    yy, xx = np.mgrid[0:H, 0:W] + 0.5; blend(img, cov(np.hypot(xx - cx, yy - cy) - r), col, a)

THEMES = {
 "Mulberry":   dict(bg=((46, 16, 44), (18, 6, 20)), tile=(58, 28, 62), tile_off=(36, 18, 40), text=(236, 222, 240), hi=(176, 120, 190), ring=(214, 160, 232), on=(120, 200, 120), warn=(205, 50, 80), dim=0.45),
 "Cloudberry": dict(bg=((252, 244, 230), (238, 222, 205)), tile=(255, 252, 244), tile_off=(232, 220, 206), text=(70, 38, 60), hi=(255, 255, 255), ring=(224, 150, 70), on=(80, 160, 90), warn=(200, 60, 80), dim=0.55),
}
def render(name, th):
    top, bot = np.array(th["bg"][0], float), np.array(th["bg"][1], float)
    t = np.linspace(0, 1, H)[:, None, None]; img = top * (1 - t) + bot * t; img = img * np.ones((1, W, 1))
    bay = np.array([[0, 2], [3, 1]]) / 4 - 0.375; img += np.tile(bay, (H // 2, W // 2))[..., None] * (255 / 31)       # dither
    dark = sum(th["tile"]) < 300
    def tile(x, y, w, h, base, art, lit, sel=False):
        d = sdf_rr(w, h, 5, 0, 0, W, H) if False else None
        sub = np.zeros((H, W)); full = sdf_rr(w, h, 5, x, y, W, H)
        face = np.array(base, float)
        if sel:                                                     # soft two-step ring that follows the tile
            blend(img, cov(full - 2.5) * (1 - cov(full - 0.5 + 0.0)), th["ring"], 0.30)
            blend(img, cov(full - 1.5) * (1 - cov(full - 0.5 + 0.0)), th["ring"], 0.55)
        # soft drop shadow, then the face with a gentle vertical gradient
        sh = sdf_rr(w, h, 5, x, y + 1.5, W, H); blend(img, cov(sh - 0.5), (0, 0, 0) if dark else (120, 90, 80), 0.28 if dark else 0.14)
        yy = np.mgrid[0:H, 0:W][0] + 0.5; g = np.clip((yy - y) / h, 0, 1)[..., None]
        blend(img, cov(full), face * (1.07 - 0.14 * g), 1.0)
        # sheen: highlight band hugging the top-left inside edge, soft (2 px falloff), not a hard line
        inner = np.clip(1 - (-full) / 2.2, 0, 1) * cov(full + 0.2)
        yy2, xx2 = np.mgrid[0:H, 0:W] + 0.5; dirk = np.clip(1 - ((xx2 - x) / w + (yy2 - y) / h) * 0.9, 0, 1)
        blend(img, inner * dirk, th["hi"], 0.30 if dark else 0.9)
        low = np.clip(1 - (-full) / 2.0, 0, 1) * cov(full + 0.2) * (1 - dirk); blend(img, low, (0, 0, 0) if dark else (150, 110, 100), 0.18)
        art(x, y, lit)
    def pedal(x, y, lit, body=(40, 150, 70)):
        b = np.array(body, float) * (1.0 if lit else th["dim"]) if dark else (np.array(body, float) * 0.9 + 255 * (0 if lit else 0.5) * 0.6)
        if not dark and not lit: b = np.array(body, float) * 0.5 + 125
        m = sdf_rr(16, 20, 3, x + 6, y + 2, W, H); yy = np.mgrid[0:H, 0:W][0] + 0.5; g = np.clip((yy - (y + 2)) / 20, 0, 1)[..., None]
        blend(img, cov(m), b * (1.18 - 0.36 * g)); blend(img, cov(m + 1.0) * (1 - cov(m + 0.0)) * 0 + np.clip(1 - (-m) / 1.6, 0, 1) * cov(m + 0.2) * 0.5, (255, 255, 255), 0.35 if lit else 0.15)
        blend(img, np.clip(1 - (-m) / 1.6, 0, 1) * cov(m + 0.2) * (np.clip((yy - (y + 12)) / 10, 0, 1)), (0, 0, 0), 0.30)
        for kx in (3, 8, 13): disc(img, x + 6 + kx, y + 6, 2.0, (235, 232, 226) if lit else (170, 165, 165)); disc(img, x + 6 + kx - 0.5, y + 5.4, 0.9, (255, 255, 255), 0.7 if lit else 0.3)
        blend(img, cov(sdf_rr(10, 4, 1.5, x + 9, y + 11, W, H)), (250, 248, 240) if lit else (190, 185, 185))
        disc(img, x + 14, y + 19.5, 2.5, (160, 160, 168) if lit else (130, 130, 135)); disc(img, x + 13.4, y + 18.8, 1.1, (230, 230, 236), 0.8 if lit else 0.3)
    def amp(x, y, lit):
        b = np.array((205, 160, 70), float) * (1.0 if lit else th["dim"] if dark else 0.6)
        blend(img, cov(sdf_rr(22, 15, 2.5, x + 3, y + 5, W, H)), (30, 24, 26) if lit else (70, 62, 64))
        blend(img, cov(sdf_rr(20, 6, 1.5, x + 4, y + 6, W, H)), b)
        for k in range(5): disc(img, x + 7 + 3.2 * k, y + 9, 0.8, (40, 30, 20))
        blend(img, cov(sdf_rr(20, 6, 1.5, x + 4, y + 13, W, H)), (60, 48, 44) if lit else (90, 80, 78))
    xs = [8 + 30 * i for i in range(5)]
    tile(xs[0], 30, 26, 26, th["tile"], lambda x, y, l: pedal(x + 2, y + 0, l), True, sel=True)
    tile(xs[1], 30, 26, 26, th["tile"], lambda x, y, l: pedal(x + 2, y + 0, l, (60, 120, 220)), True)
    tile(xs[2], 30, 26, 26, th["tile"], amp, True)
    tile(xs[3], 30, 26, 26, th["tile_off"], lambda x, y, l: pedal(x + 2, y + 0, l, (150, 80, 210)), False)
    tile(xs[4], 30, 26, 26, th["tile_off"], amp, False)
    # bars + status: soft ends
    for (x0, v, col) in ((8, 0.6, th["on"]), (84, 0.85, th["warn"])):
        blend(img, cov(sdf_rr(68, 6, 3, x0, 100, W, H)), (0, 0, 0) if dark else (150, 120, 110), 0.25 if dark else 0.16)
        m = cov(sdf_rr(68 * v, 6, 3, x0, 100, W, H)); blend(img, m, col)
    pil = Image.fromarray(q565(img)); d = ImageDraw.Draw(pil); f = ImageFont.load_default()
    d.rounded_rectangle([6, 5, 40, 19], 6, fill=tuple(int(c) for c in th["ring"])); d.text((11, 6), "P08", font=f, fill=(30, 12, 30))
    d.text((46, 6), "UKInvasion*", font=f, fill=tuple(th["text"])); d.text((8, 62), name, font=f, fill=tuple(th["text"]))
    d.text((8, 74), "lit  lit  amp  off  off", font=f, fill=tuple(int(c * 0.8) for c in th["text"]))
    return pil
out = Image.new("RGB", (W * 2 + 8, H), (0, 0, 0))
for i, (n, t) in enumerate(THEMES.items()): out.paste(render(n, t), (i * (W + 8), 0))
out.save("ui/berry/soft_1x.png"); out.resize((out.width * 4, out.height * 4), Image.NEAREST).save("ui/berry/soft_4x.png"); print("ok")
