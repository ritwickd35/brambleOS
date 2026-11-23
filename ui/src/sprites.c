/* Procedural gear sprites (code, no bitmaps): 28x24 cell at (x, y). kind: 0 NR 1 FX1 2 DRV 3 AMP 4 IR 5 EQ 6 FX2 7 DLY 8 RVB. */
#include "pages.h"
#define RGB(r, g, b) ((rgb_t){r, g, b})
static rgb_t lite(rgb_t c, int lit)   /* off = grey and faded, so on/off reads at a glance (also on a poor-angle screen) */
{ const theme_t *t = gfx_theme(); if (lit) return c; int l = (c.r * 3 + c.g * 6 + c.b) / 10; if (t->dark) { l = l * 25 / 100 + 46; return RGB(l, l * 9 / 10, l); } l = l * 28 / 100 + 112; return RGB(l, l, l); }
static void shine(float cx, float cy, float r, rgb_t c, int lit) { gfx_disc(cx, cy, r, c, 1); gfx_disc(cx - r * 0.3f, cy - r * 0.35f, r * 0.4f, RGB(255, 255, 255), lit ? 0.35f : 0.15f); }
static void pedal(float x, float y, rgb_t body, int lit, int knobs)
{
    rgb_t b = lite(body, lit), hi = RGB(b.r > 120 ? 255 : b.r + 135, b.g > 120 ? 255 : b.g + 135, b.b > 120 ? 255 : b.b + 135);
    float bx = x + 6, by = y + 2; gfx_rrect(bx, by, 16, 20, 3, b, 1); gfx_rrect(bx, by, 16, 9, 3, hi, lit ? 0.22f : 0.10f); gfx_rrect(bx, by + 12, 16, 8, 3, RGB(0, 0, 0), 0.22f);
    rgb_t kn = lite(RGB(235, 232, 226), lit); for (int k = 0; k < knobs; k++) shine(bx + 8 + (k - (knobs - 1) * 0.5f) * 5.0f, by + 4.2f, 2.0f, kn, lit);
    gfx_rrect(bx + 3, by + 9, 10, 4, 1.5f, lite(RGB(250, 248, 240), lit), 1); shine(bx + 8, by + 17, 2.4f, lite(RGB(165, 165, 172), lit), lit);
}
static void amp(float x, float y, int lit, int nam)
{
    gfx_rrect(x + 3, y + 5, 22, 15, 2.5f, lite(RGB(30, 24, 26), lit), 1); gfx_rrect(x + 4, y + 6, 20, 6, 1.5f, lite(nam ? RGB(150, 110, 215) : RGB(205, 160, 70), lit), 1);
    for (int k = 0; k < 5; k++) gfx_disc(x + 7 + 3.2f * k, y + 9, 0.8f, RGB(40, 30, 20), 1); gfx_rrect(x + 4, y + 13, 20, 6, 1.5f, lite(RGB(60, 48, 44), lit), 1);
}
static void cab(float x, float y, int lit)
{
    gfx_rrect(x + 4, y + 2, 20, 20, 2.5f, lite(RGB(32, 28, 30), lit), 1);
    for (int k = 0; k < 5; k++) gfx_rrect(x + 6, y + 5 + 3 * k, 16, 1.2f, 0.6f, lite(RGB(120, 105, 85), lit), 0.8f);
    shine(x + 14, y + 12, 5, lite(RGB(60, 52, 50), lit), lit);
}
static void eq(float x, float y, int lit)
{
    gfx_rrect(x + 3, y + 3, 22, 18, 3, lite(RGB(50, 46, 62), lit), 1); static const u8 h[5] = {6, 11, 4, 9, 7};
    for (int k = 0; k < 5; k++) { gfx_rrect(x + 6 + 3.6f * k, y + 5, 1.2f, 14, 0.6f, lite(RGB(24, 20, 30), lit), 1); gfx_rrect(x + 5 + 3.6f * k, y + 16 - h[k], 3.2f, 2.4f, 1.0f, lite(RGB(232, 100, 170), lit), 1); }
}
void sprite(int kind, float x, float y, int lit, int variant)
{
    static const rgb_t col[9] = {{50, 100, 190}, {40, 160, 90}, {210, 70, 70}, {0, 0, 0}, {0, 0, 0}, {0, 0, 0}, {230, 140, 50}, {60, 130, 230}, {150, 90, 215}};
    switch (kind) { case 3: amp(x, y, lit, variant); break; case 4: cab(x, y, lit); break; case 5: eq(x, y, lit); break; default: pedal(x, y, col[kind], lit, 3); }
}
