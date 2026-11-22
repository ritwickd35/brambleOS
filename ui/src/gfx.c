#define FONT_DATA_IMPL
#include "gfx.h"
typedef struct { const theme_t *t; int x1, x2, y1, y2; u16 *px; } ctx_t;
#ifdef PEDAL
/* The image has no RAM of its own and no RAM address is known to be free, so the drawing state lives on the hook's stack
 * and its address is kept in register r10 (reserved with -ffixed-r10; the hook saves and restores the caller's r10). */
register ctx_t *CTXR asm("$r10");
#define CTX (*CTXR)
void *gfx_bind(void *c) { void *o = (void *)CTXR; CTXR = (ctx_t *)c; return o; }
#else
static ctx_t CTXV; static ctx_t *const CTXP = &CTXV; 
#define CTX (*CTXP)
#endif
#define T (CTX.t)
#define X1 (CTX.x1)
#define X2 (CTX.x2)
#define Y1 (CTX.y1)
#define Y2 (CTX.y2)
#define PX (CTX.px)
#define RGB(r, g, b) ((rgb_t){r, g, b})
const theme_t THEMES[] = {
 /* Mulberry */   {RGB(156, 96, 156), RGB(88, 46, 96), RGB(138, 86, 142), RGB(94, 54, 100), RGB(248, 238, 250), RGB(208, 184, 216), RGB(176, 120, 190), RGB(214, 160, 232), RGB(120, 200, 120), RGB(210, 52, 84), RGB(62, 32, 66), RGB(30, 12, 30), 1},
 /* Cloudberry */ {RGB(252, 244, 230), RGB(238, 222, 205), RGB(255, 252, 244), RGB(232, 220, 206), RGB(70, 38, 60), RGB(140, 110, 130), RGB(255, 255, 255), RGB(224, 150, 70), RGB(80, 160, 90), RGB(200, 60, 80), RGB(222, 206, 192), RGB(255, 250, 240), 0},
};
const theme_t *gfx_theme(void) { return (const theme_t *)T; }
void gfx_begin(int x1, int x2, int y1, int y2, u16 *px, const theme_t *t) { X1 = x1; X2 = x2; Y1 = y1; Y2 = y2; PX = px; T = (const theme_t *)t; }

static float fsq(float x) { if (x <= 0) return 0; float y = x > 1 ? x * 0.5f : 1.0f; for (int i = 0; i < 6; i++) y = 0.5f * (y + x / y); return y; }   /* Newton, no libm */
static float fabsf_(float x) { return x < 0 ? -x : x; }
float gfx_sin(float deg)                                                /* degrees, ~0.001 */
{
    while (deg < 0) deg += 360; while (deg >= 360) deg -= 360; float s = 1; if (deg >= 180) { deg -= 180; s = -1; } if (deg > 90) deg = 180 - deg;
    float x = deg * 0.0174533f, x2 = x * x; return s * x * (1 - x2 / 6 * (1 - x2 / 20 * (1 - x2 / 42)));
}
static float atan2_(float y, float x)                                   /* ~0.01 rad */
{
    float ax = fabsf_(x), ay = fabsf_(y), mn = ax < ay ? ax : ay, mx = ax > ay ? ax : ay; if (mx == 0) return 0;
    float a = mn / mx, s = a * a, r = ((-0.0464964749f * s + 0.15931422f) * s - 0.327622764f) * s * a + a;
    if (ay > ax) r = 1.57079637f - r; if (x < 0) r = 3.14159274f - r; return y < 0 ? -r : r;
}
rgb_t rgbf(rgb_t a, rgb_t b, float t) { return RGB((u8)(a.r + (b.r - a.r) * t), (u8)(a.g + (b.g - a.g) * t), (u8)(a.b + (b.b - a.b) * t)); }

static inline void put(int x, int y, rgb_t c, int a)                    /* a: 0..256 */
{
    if (a <= 0) return;
    u16 *p = &PX[(y - Y1) * (X2 - X1 + 1) + (x - X1)], v;
    if (a >= 256) { v = (u16)(((c.r >> 3) << 11) | ((c.g >> 2) << 5) | (c.b >> 3)); *p = (u16)((v >> 8) | (v << 8)); return; }   /* opaque: no read */
    v = *p; v = (u16)((v >> 8) | (v << 8));
    int r = (v >> 11) << 3, g = ((v >> 5) & 63) << 2, b = (v & 31) << 3; r |= r >> 5; g |= g >> 6; b |= b >> 5;
    if (a >= 256) { r = c.r; g = c.g; b = c.b; } else { r += ((c.r - r) * a) >> 8; g += ((c.g - g) * a) >> 8; b += ((c.b - b) * a) >> 8; }
    v = (u16)(((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)); *p = (u16)((v >> 8) | (v << 8));
}
static inline int cov(float d, float a) { float c = 0.5f - d; return c <= 0 ? 0 : (int)((c >= 1 ? 1 : c) * a * 256.0f); }
static void box(float x, float y, float w, float h, int *x0, int *x1, int *y0, int *y1)
{
    *x0 = (int)(x) - 1; *x1 = (int)(x + w) + 2; *y0 = (int)(y) - 1; *y1 = (int)(y + h) + 2;
    if (*x0 < X1) *x0 = X1; if (*x1 > X2 + 1) *x1 = X2 + 1; if (*y0 < Y1) *y0 = Y1; if (*y1 > Y2 + 1) *y1 = Y2 + 1;
}
static float sdf_rr(float px, float py, float x, float y, float w, float h, float r)
{
    float qx = fabsf_(px - (x + w * 0.5f)) - (w * 0.5f - r), qy = fabsf_(py - (y + h * 0.5f)) - (h * 0.5f - r);
    if (qx > 0 && qy > 0) return fsq(qx * qx + qy * qy) - r; return (qx > qy ? qx : qy) - r;
}

void gfx_bg(void)
{
    /* Vertical gradient, posterised into visible bands with a 4x4 ordered dither between them (the retro look).
     * Integer per pixel: each row has a band level q and a fraction f (0..15) per channel; a pixel takes q+1 if f > bayer. */
    static const unsigned char bay[16] = {0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5};
    for (int y = Y1; y <= Y2; y++) {
        int q[3], f[3], c0[3] = {T->bg0.r, T->bg0.g, T->bg0.b}, c1[3] = {T->bg1.r, T->bg1.g, T->bg1.b};
        for (int k = 0; k < 3; k++) { int v16 = (c0[k] * 16 * 127 + (c1[k] - c0[k]) * 16 * y) / 127 * 16 / 12 / 16;   /* value / 12 in 1/16 */
            int v = (c0[k] * 127 + (c1[k] - c0[k]) * y) * 16 / (127 * 12); q[k] = v >> 4; f[k] = v & 15; (void)v16; }
        u16 *row = &PX[(y - Y1) * (X2 - X1 + 1)]; const unsigned char *by = &bay[(y & 3) * 4];
        for (int x = X1; x <= X2; x++) { int th = by[x & 3], o[3];
            for (int k = 0; k < 3; k++) { int v = (q[k] + (f[k] > th)) * 12; o[k] = v > 255 ? 255 : v; }
            u16 v = (u16)(((o[0] >> 3) << 11) | ((o[1] >> 2) << 5) | (o[2] >> 3)); row[x - X1] = (u16)((v >> 8) | (v << 8)); } }
}
static float smin(float a, float b, float k) { float h = 0.5f + 0.5f * (b - a) / k; h = h < 0 ? 0 : h > 1 ? 1 : h; return b + (a - b) * h - k * h * (1 - h); }
void gfx_tray(float x, float y, float w, float h, float x2, float y2, float w2, float h2, float r, rgb_t c, float a)
{   /* union of two rounded rects with a smooth (filleted) inner corner, drawn as one translucent layer */
    int x0, x1, y0, y1; box(x < x2 ? x : x2, y < y2 ? y : y2, (x + w > x2 + w2 ? x + w : x2 + w2) - (x < x2 ? x : x2), (y + h > y2 + h2 ? y + h : y2 + h2) - (y < y2 ? y : y2), &x0, &x1, &y0, &y1);
    for (int py = y0; py < y1; py++) for (int px = x0; px < x1; px++) {
        float d = smin(sdf_rr(px + 0.5f, py + 0.5f, x, y, w, h, r), sdf_rr(px + 0.5f, py + 0.5f, x2, y2, w2, h2, r), 4.0f); put(px, py, c, cov(d, a)); }
}
void gfx_rrect(float x, float y, float w, float h, float r, rgb_t c, float a)
{
    /* Only pixels near the outline need the distance maths; the inside (shrunk by the corner radius + 1 px) is solid. */
    int x0, x1, y0, y1; box(x, y, w, h, &x0, &x1, &y0, &y1); int A = (int)(a * 256.0f);
    int ix0 = (int)(x + r + 1), ix1 = (int)(x + w - r - 1), iy0 = (int)(y + 1), iy1 = (int)(y + h - 1);   /* inner band, full rows */
    int jx0 = (int)(x + 1), jx1 = (int)(x + w - 1), jy0 = (int)(y + r + 1), jy1 = (int)(y + h - r - 1);   /* inner band, full cols */
    for (int py = y0; py < y1; py++) for (int px = x0; px < x1; px++) {
        if ((px >= ix0 && px < ix1 && py >= iy0 && py < iy1) || (px >= jx0 && px < jx1 && py >= jy0 && py < jy1)) { put(px, py, c, A); continue; }
        put(px, py, c, cov(sdf_rr(px + 0.5f, py + 0.5f, x, y, w, h, r), a)); }
}
void gfx_rring(float x, float y, float w, float h, float r, float th, rgb_t c, float a)     /* rounded outline */
{
    int x0, x1, y0, y1; box(x - th, y - th, w + 2 * th, h + 2 * th, &x0, &x1, &y0, &y1);
    for (int py = y0; py < y1; py++) for (int px = x0; px < x1; px++) { float d = sdf_rr(px + 0.5f, py + 0.5f, x, y, w, h, r); put(px, py, c, cov(fabsf_(d) - th * 0.5f, a)); }
}
void gfx_disc(float cx, float cy, float r, rgb_t c, float a)
{
    int x0, x1, y0, y1; box(cx - r, cy - r, 2 * r, 2 * r, &x0, &x1, &y0, &y1);
    for (int py = y0; py < y1; py++) for (int px = x0; px < x1; px++) { float dx = px + 0.5f - cx, dy = py + 0.5f - cy; put(px, py, c, cov(fsq(dx * dx + dy * dy) - r, a)); }
}
void gfx_arc(float cx, float cy, float r, float th, float a0, float a1, rgb_t c, float a)
{
    int x0, x1, y0, y1; box(cx - r - th, cy - r - th, 2 * (r + th), 2 * (r + th), &x0, &x1, &y0, &y1);
    while (a0 < 0) a0 += 360; while (a1 < 0) a1 += 360; while (a0 >= 360) a0 -= 360; while (a1 >= 360) a1 -= 360; int full = (a0 == a1);
    for (int py = y0; py < y1; py++) for (int px = x0; px < x1; px++) {
        float dx = px + 0.5f - cx, dy = py + 0.5f - cy, d = fsq(dx * dx + dy * dy); int k = cov(fabsf_(d - r) - th * 0.5f, a); if (!k) continue;
        float an = atan2_(dy, dx) * 57.29578f; if (an < 0) an += 360; int in = full || (a0 <= a1 ? (an >= a0 && an <= a1) : (an >= a0 || an <= a1)); if (in) put(px, py, c, k); }
}
void gfx_tri(float x0_, float y0_, float x1_, float y1_, float x2_, float y2_, rgb_t c, float a)
{
    float xs[3] = {x0_, x1_, x2_}, ys[3] = {y0_, y1_, y2_}; float mnx = xs[0], mxx = xs[0], mny = ys[0], mxy = ys[0];
    for (int i = 1; i < 3; i++) { if (xs[i] < mnx) mnx = xs[i]; if (xs[i] > mxx) mxx = xs[i]; if (ys[i] < mny) mny = ys[i]; if (ys[i] > mxy) mxy = ys[i]; }
    int bx0, bx1, by0, by1; box(mnx, mny, mxx - mnx, mxy - mny, &bx0, &bx1, &by0, &by1);
    float ar = (x1_ - x0_) * (y2_ - y0_) - (x2_ - x0_) * (y1_ - y0_); float sg = ar > 0 ? 1.0f : -1.0f;
    for (int py = by0; py < by1; py++) for (int px = bx0; px < bx1; px++) {
        float m = 1e9f; for (int i = 0; i < 3; i++) { int j = (i + 1) % 3; float ex = xs[j] - xs[i], ey = ys[j] - ys[i], n = fsq(ex * ex + ey * ey);
            float d = sg * (ex * (py + 0.5f - ys[i]) - ey * (px + 0.5f - xs[i])) / n; if (d < m) m = d; }
        put(px, py, c, cov(-m, a)); }
}
void gfx_bar(float x, float y, float w, float h, float v, rgb_t c)
{
    gfx_rrect(x, y, w, h, h * 0.5f, T->track, 1);
    if (v > 0) { float fw = w * v; if (fw < h) fw = h; gfx_rrect(x, y, fw, h, h * 0.5f, c, 1); gfx_rrect(x, y, fw, h * 0.5f, h * 0.25f, RGB(255, 255, 255), 0.18f); }
}
void gfx_tile(float x, float y, float w, float h, int lit, int sel, float r)
{
    rgb_t base = T->tile, blk = T->dark ? RGB(0, 0, 0) : RGB(120, 90, 80);
    if (sel) { gfx_rrect(x - 2.5f, y - 2.5f, w + 5, h + 5, r + 2.5f, T->ring, 0.28f); gfx_rrect(x - 1.5f, y - 1.5f, w + 3, h + 3, r + 1.5f, T->ring, 0.6f); }
    if (!lit) {   /* off: an empty, sunken slot - dashed-looking faint outline, no fill */
        gfx_rrect(x, y, w, h, r, blk, T->dark ? 0.18f : 0.05f); gfx_rrect(x + 0.5f, y + 0.5f, w - 1, h - 1, r - 0.5f, T->track, T->dark ? 0.25f : 0.20f);
        gfx_rrect(x + 1.5f, y + 1.5f, w - 3, h - 3, r - 1.5f, blk, T->dark ? 0.22f : 0.04f); return; }
    /* on: raised, bright, with a thin accent rim */
    gfx_rrect(x - 2.5f, y - 2.5f, w + 5, h + 5, r + 2.5f, T->on, 0.22f);                         /* soft glow */
    gfx_rrect(x - 1.2f, y - 1.2f, w + 2.4f, h + 2.4f, r + 1.2f, T->on, 0.95f);                    /* bright rim */
    gfx_rrect(x, y + 1.5f, w, h, r, blk, T->dark ? 0.28f : 0.14f);
    gfx_rrect(x, y, w, h, r, base, 1);
    gfx_rrect(x + 1, y + 1, w - 2, h * 0.45f, r - 1, T->hi, T->dark ? 0.10f : 0.55f);                 /* sheen: soft light on the upper half */
    gfx_rrect(x + 1, y + h * 0.62f, w - 2, h * 0.36f, r - 1, blk, T->dark ? 0.10f : 0.07f);
}
void gfx_led(float x, float y, int on) { if (!on) return; gfx_disc(x, y, 3.4f, T->on, 0.30f); gfx_disc(x, y, 1.9f, T->on, 1); gfx_disc(x - 0.5f, y - 0.6f, 0.8f, RGB(255, 255, 255), 0.6f); }
int gfx_text_w(const font_t *f, const char *s) { int w = 0; for (; *s; s++) { int i = *s - f->first; if (i >= 0 && i < f->count) w += f->g[i].adv; } return w; }
void gfx_text(float x, float y, const char *s, const font_t *f, rgb_t c, const char *anchor, float a)
{
    int w = gfx_text_w(f, s); float x0 = x, y0 = y;
    if (anchor[0] == 'm') x0 = x - w * 0.5f; else if (anchor[0] == 'r') x0 = x - w;
    if (anchor[1] == 'm') y0 = y - f->height * 0.5f; else if (anchor[1] == 'b') y0 = y - f->height;
    int cx = (int)(x0 + 0.5f), cy = (int)(y0 + 0.5f);
    for (; *s; s++) { int gi = *s - f->first; if (gi < 0 || gi >= f->count) continue; const glyph_t *g = &f->g[gi];
        for (int j = 0; j < g->h; j++) { int py = cy + g->yo + j; if (py < Y1 || py > Y2) continue;
            for (int i = 0; i < g->w; i++) { int px = cx + g->xo + i; if (px < X1 || px > X2) continue; int k = j * g->w + i, q = (f->bits[g->off + (k >> 2)] >> (6 - 2 * (k & 3))) & 3;
                if (q) put(px, py, c, (int)(q * 85 * a)); } }
        cx += g->adv; }
}
void gfx_pill(float x, float y, float w, float h, const char *s, const font_t *f, int on, rgb_t fill)
{
    gfx_rrect(x, y, w, h, h * 0.5f, fill, 1); gfx_text(x + w * 0.5f, y + h * 0.5f, s, f, on ? T->ink : T->sub, "mm", 1);
}
