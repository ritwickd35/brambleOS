#include "pages.h"
#define RGB(r, g, b) ((rgb_t){r, g, b})
/* Edit page (Berry design). Layout (160 x 128):
 *   0..12   preset + name
 *  13..42   the 9 blocks in chain order, two rows (5 + 4), name inside, the edited one ringed
 *  45..84   model card: block picture, block name, model, maker, ON/OFF badge, Basic/NAM switch
 *  86..127  knobs, 4 per page (ring + value, or a switch for on/off knobs), page dots
 * The highlighted item is what the knob changes: a knob (ksel), the model or the AMP mode (ekind). */
static const char *const LAB[9] = {"NR", "FX1", "DRV", "AMP", "IR", "EQ", "FX2", "DLY", "RVB"};
static const rgb_t GC[9] = {{40, 90, 170}, {40, 140, 80}, {200, 50, 50}, {220, 170, 60}, {70, 60, 50}, {60, 55, 70}, {190, 130, 40}, {50, 130, 220}, {140, 90, 210}};
static void itoa2(int v, char *s) { char t[12]; int n = 0; if (v < 0) v = 0; do { t[n++] = '0' + v % 10; v /= 10; } while (v); for (int i = 0; i < n; i++) s[i] = t[n - 1 - i]; s[n] = 0; }
static rgb_t dim(rgb_t c, const theme_t *t) { int l = (c.r * 3 + c.g * 6 + c.b) / 10; l = t->dark ? l * 30 / 100 + 34 : l / 6 + 190; return RGB(l, l * 9 / 10, l); }
static void ring(float x, float y, float w, float h, float r) { const theme_t *t = gfx_theme(); gfx_rring(x - 2, y - 2, w + 4, h + 4, r + 2, 2.2f, t->ring, 1); }
void page_edit(const model_t *m)
{
    const theme_t *t = gfx_theme(); char b[24]; int sel = m->sel < 0 ? 0 : m->sel, on = m->on[sel], k = m->ekind, sx = 0, sy = 0;
    rgb_t trk = t->dark ? rgbf(t->bg1, RGB(10, 0, 14), 0.66f) : rgbf(t->bg1, t->text, 0.26f);        /* inactive part: dark */
    rgb_t act = t->dark ? rgbf(t->ring, RGB(255, 255, 255), 0.38f) : t->ring;                        /* active part: bright */
    gfx_bg();
    /* header */
    b[0] = 'P'; b[1] = '0' + (m->preset / 10) % 10; b[2] = '0' + m->preset % 10; b[3] = 0;
    gfx_pill(4, 1, 24, 10, b, &FONT7, 1, t->ring); gfx_text(32, 6, m->name, &FONT9, t->text, "lm", 1);
    if (m->edited) gfx_text(32 + gfx_text_w(&FONT9, m->name) + 2, 6, "*", &FONT9, t->sub, "lm", 1);
    /* chain: 2 rows of wide tiles */
    for (int j = 0; j < 9; j++) { int i = m->order[j] < 9 ? m->order[j] : j, o = m->on[i]; float x = 4 + (j % 5) * 31, y = 13 + (j / 5) * 16; rgb_t c = o ? GC[i] : dim(GC[i], t);
        if (i == sel) { sx = (int)x; sy = (int)y; }
        gfx_rrect(x, y, 28, 13, 4, c, 1); if (o) gfx_rrect(x + 1, y + 1, 26, 5, 3, RGB(255, 255, 255), 0.18f);
        gfx_text(x + 14, y + 7, LAB[i], &FONT9, o ? RGB(255, 255, 255) : (t->dark ? RGB(150, 130, 150) : RGB(120, 110, 115)), "mm", 1); }
    gfx_rring(sx - 2.5f, sy - 2.5f, 33, 18, 6.5f, 2, t->ring, 1);
    /* model card */
    gfx_rrect(4, 45, 152, 39, 7, t->dark ? RGB(20, 0, 24) : t->text, t->dark ? 0.30f : 0.07f);
    gfx_tile(8, 50, 28, 28, on, 0, 6); sprite(sel, 7, 50.5f, on, sel == 3 ? m->nam : 0);
    if (k == 2) { gfx_rrect(46, 48, 72, 34, 6, t->ring, 0.30f); gfx_rring(45.5f, 47.5f, 73, 35, 6.5f, 1.6f, t->ring, 1); }
    gfx_text(50, 52, LAB[sel], &FONT7, t->sub, "lm", 1);
    gfx_text(50, 64, m->mname, gfx_text_w(&FONT16, m->mname) <= 64 ? &FONT16 : &FONT12, t->text, "lm", 1);
    if (m->brand[0]) gfx_text(50, 76.5f, m->brand, &FONT7, t->sub, "lm", 1);
    gfx_pill(122, 50, 30, 13, on ? "ON" : "OFF", &FONT9, on, on ? t->on : t->track);
    if (sel == 3) { if (k == 3) ring(118, 68, 34, 12, 6);
        gfx_rrect(118, 68, 34, 12, 6, trk, 1); gfx_rrect(m->nam ? 135 : 119, 69, 16, 10, 5, act, 1);
        gfx_text(127, 74, "B", &FONT7, m->nam ? t->sub : t->ink, "mm", 1); gfx_text(143, 74, "N", &FONT7, m->nam ? t->ink : t->sub, "mm", 1); }
    /* knobs: 4 per page; the page follows the highlighted knob */
    int page = (k == 0 && m->ksel > 0) ? m->ksel / 4 : 0, n = m->nk - page * 4; if (n > 4) n = 4;
    for (int c = 0; c < n; c++) { int i = page * 4 + c, hl = k == 0 && i == m->ksel; float cx = 22 + 39 * c, cy = 100;
        if (hl) gfx_rrect(cx - 18, 87, 36, 36, 8, t->ring, 0.25f);
        if (m->kmx[i] == 1) {                                                                       /* on/off knob: a switch */
            int on1 = m->kraw[i] > 0; gfx_rrect(cx - 11, cy - 5, 22, 10, 5, on1 ? act : trk, 1); gfx_disc(on1 ? cx + 6 : cx - 6, cy, 3.6f, RGB(255, 255, 255), 1);
        } else {
            gfx_arc(cx, cy, 10.5f, 3.4f, 135, 45, trk, 1); if (m->kv[i] > 0) gfx_arc(cx, cy, 10.5f, 3.4f, 135, 135 + 2.7f * m->kv[i], act, 1);
            itoa2(m->kmx[i] > 1 && m->kmx[i] <= 30 ? m->kraw[i] : m->kv[i], b); gfx_text(cx, cy, b, &FONT9, hl ? t->text : t->sub, "mm", 1); }
        gfx_text(cx, 118, m->kn[i], &FONT7, hl ? t->text : t->sub, "mm", 1); }
    /* page dots */
    int pages = (m->nk + 3) / 4; for (int p = 0; p < pages && pages > 1; p++) gfx_disc(80 - 3.5f * (pages - 1) + 7 * p, 125.5f, p == page ? 2.4f : 1.7f, p == page ? act : trk, 1);
}
