#include "pages.h"
#define RGB(r, g, b) ((rgb_t){r, g, b})
static const char *const LAB[9] = {"NR", "FX1", "DRV", "AMP", "IR", "EQ", "FX2", "DLY", "RVB"};
static void itoa2(int v, char *s) { char t[12]; int n = 0; if (v < 0) v = 0; do { t[n++] = '0' + v % 10; v /= 10; } while (v); for (int i = 0; i < n; i++) s[i] = t[n - 1 - i]; s[n] = 0; }
void page_edit(const model_t *m)
{
    const theme_t *t = gfx_theme(); char b[24];
    gfx_bg();
    /* header: preset + name */
    b[0] = 'P'; b[1] = '0' + (m->preset / 10) % 10; b[2] = '0' + m->preset % 10; b[3] = 0;
    gfx_pill(4, 3, 26, 12, b, &FONT9, 1, t->ring); gfx_text(35, 9, m->name, &FONT9, t->text, "lm", 1);
    if (m->edited) gfx_text(35 + gfx_text_w(&FONT9, m->name) + 2, 9, "*", &FONT9, t->sub, "lm", 1);
    /* block strip: 9 mini squares in chain order (gear colour when on, empty slot when off); the edited one ringed */
    static const rgb_t GC[9] = {{40, 90, 170}, {40, 140, 80}, {200, 50, 50}, {220, 170, 60}, {70, 60, 50}, {60, 55, 70}, {190, 130, 40}, {50, 130, 220}, {140, 90, 210}};
    for (int i = 0; i < 9; i++) { float x = 4 + i * 17; int s = i == m->sel;
        gfx_tile(x, 20, 15, 13, m->on[i], s, 3); if (m->on[i]) gfx_rrect(x + 3, 23, 9, 7, 2, GC[i], 1); }
    /* model card */
    int sel = m->sel < 0 ? 0 : m->sel, on = m->on[sel];
    gfx_tray(4, 38, 152, 40, 4, 38, 152, 40, 7, t->dark ? RGB(20, 0, 24) : t->text, t->dark ? 0.30f : 0.07f);
    gfx_tile(8, 42, 32, 32, on, 0, 6); sprite(sel, 11, 45, on, sel == 3 ? m->nam : 0);
    gfx_text(46, 45, LAB[sel], &FONT7, t->sub, "lm", 1); gfx_text(46, 56, m->mname, gfx_text_w(&FONT16, m->mname) <= 76 ? &FONT16 : &FONT12, t->text, "lm", 1);
    gfx_text(46, 70, m->brand, &FONT7, t->sub, "lm", 1);
    gfx_pill(124, 43, 28, 13, on ? "ON" : "OFF", &FONT9, on, on ? t->on : t->track);
    if (sel == 3) { gfx_rrect(118, 61, 34, 12, 6, t->track, 1); gfx_rrect(m->nam ? 135 : 119, 62, 16, 10, 5, t->ring, 1);
        gfx_text(127, 67, "B", &FONT7, m->nam ? t->sub : t->ink, "mm", 1); gfx_text(143, 67, "N", &FONT7, m->nam ? t->ink : t->sub, "mm", 1); }
    /* knobs: 4 per page, rings with value; the highlighted one in the accent colour */
    int page = m->ksel / 4, n = m->nk - page * 4; if (n > 4) n = 4;
    for (int k = 0; k < n; k++) { int i = page * 4 + k, hl = i == m->ksel; float cx = 22 + 39 * k, cy = 96; rgb_t c = hl ? t->ring : t->sub;
        gfx_arc(cx, cy, 11, 3, 135, 45, t->track, 1); if (m->kv[i] > 0) gfx_arc(cx, cy, 11, 3, 135, 135 + 2.7f * m->kv[i], c, 1);
        itoa2(m->kv[i], b); gfx_text(cx, cy, b, &FONT9, hl ? t->text : t->sub, "mm", 1); gfx_text(cx, 113, m->kn[i], &FONT7, c, "mm", 1); }
    if (m->nk > 4) for (int p = 0; p * 4 < m->nk; p++) gfx_disc(80 - 3 * ((m->nk + 3) / 4 - 1) + 6 * p, 122, 1.5f, p == page ? t->ring : t->track, 1);
}
