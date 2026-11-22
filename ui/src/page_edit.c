#include "pages.h"
#define RGB(r, g, b) ((rgb_t){r, g, b})
/* Edit page (Berry design): header, block strip, model card (ON, model, Basic/NAM), 4 knobs per page, hint line.
 * The highlighted item is what the knob changes: a knob (ksel), on/off, the model or the AMP mode (ekind). */
static const char *const LAB[9] = {"NR", "FX1", "DRV", "AMP", "IR", "EQ", "FX2", "DLY", "RVB"};
static const rgb_t GC[9] = {{40, 90, 170}, {40, 140, 80}, {200, 50, 50}, {220, 170, 60}, {70, 60, 50}, {60, 55, 70}, {190, 130, 40}, {50, 130, 220}, {140, 90, 210}};
static void itoa2(int v, char *s) { char t[12]; int n = 0; if (v < 0) v = 0; do { t[n++] = '0' + v % 10; v /= 10; } while (v); for (int i = 0; i < n; i++) s[i] = t[n - 1 - i]; s[n] = 0; }
static rgb_t dim(rgb_t c, const theme_t *t) { int l = (c.r * 3 + c.g * 6 + c.b) / 10; l = t->dark ? l * 30 / 100 + 34 : l / 6 + 190; return RGB(l, l * 9 / 10, l); }
static void ring(float x, float y, float w, float h, float r) { const theme_t *t = gfx_theme(); gfx_rring(x - 2, y - 2, w + 4, h + 4, r + 2, 2.2f, t->ring, 1); }
void page_edit(const model_t *m)
{
    const theme_t *t = gfx_theme(); char b[24]; int sel = m->sel < 0 ? 0 : m->sel, on = m->on[sel], k = m->ekind;
    gfx_bg();
    /* header */
    b[0] = 'P'; b[1] = '0' + (m->preset / 10) % 10; b[2] = '0' + m->preset % 10; b[3] = 0;
    gfx_pill(4, 1, 24, 10, b, &FONT7, 1, t->ring); gfx_text(32, 6, m->name, &FONT9, t->text, "lm", 1);
    if (m->edited) gfx_text(32 + gfx_text_w(&FONT9, m->name) + 2, 6, "*", &FONT9, t->sub, "lm", 1);
    /* block strip, chain order */
    for (int j = 0; j < 9; j++) { int i = m->order[j] < 9 ? m->order[j] : j; float x = 4 + j * 17; int s = i == sel, o = m->on[i]; rgb_t c = o ? GC[i] : dim(GC[i], t);
        if (s) { gfx_rrect(x - 2, 12, 19, 17, 5, t->ring, 0.3f); gfx_rrect(x - 1, 13, 17, 15, 4, t->ring, 1); }
        gfx_rrect(x, 14, 15, 13, 3, c, 1); if (o) gfx_rrect(x + 1, 15, 13, 5, 2, RGB(255, 255, 255), 0.18f);
        gfx_text(x + 7.5f, 20.5f, LAB[i], &FONT8, o ? RGB(255, 255, 255) : (t->dark ? RGB(150, 130, 150) : RGB(120, 110, 115)), "mm", 1); }
    /* model card */
    gfx_rrect(4, 32, 152, 42, 7, t->dark ? RGB(20, 0, 24) : t->text, t->dark ? 0.30f : 0.07f);
    gfx_tile(8, 36, 34, 34, on, 0, 6); sprite(sel, 12, 40, on, sel == 3 ? m->nam : 0);
    if (k == 2) ring(46, 36, 72, 26, 5);
    gfx_text(48, 41, LAB[sel], &FONT7, t->sub, "lm", 1);
    gfx_text(48, 52, m->mname, gfx_text_w(&FONT16, m->mname) <= 68 ? &FONT16 : &FONT12, t->text, "lm", 1);
    if (m->brand[0]) gfx_text(48, 66, m->brand, &FONT7, t->sub, "lm", 1);
    if (k == 1) ring(122, 37, 30, 13, 6.5f);
    gfx_pill(122, 37, 30, 13, on ? "ON" : "OFF", &FONT9, on, on ? t->on : t->track);
    if (sel == 3) { if (k == 3) ring(118, 56, 34, 12, 6);
        gfx_rrect(118, 56, 34, 12, 6, t->track, 1); gfx_rrect(m->nam ? 135 : 119, 57, 16, 10, 5, t->ring, 1);
        gfx_text(127, 62, "B", &FONT7, m->nam ? t->sub : t->ink, "mm", 1); gfx_text(143, 62, "N", &FONT7, m->nam ? t->ink : t->sub, "mm", 1); }
    /* knobs: 4 per page; the page follows the highlighted knob */
    int page = (k == 0 && m->ksel > 0) ? m->ksel / 4 : 0, n = m->nk - page * 4; if (n > 4) n = 4;
    for (int c = 0; c < n; c++) { int i = page * 4 + c, hl = k == 0 && i == m->ksel; float cx = 22 + 39 * c, cy = 96; rgb_t col = hl ? t->ring : t->sub;
        if (hl) gfx_rrect(cx - 18, 79, 36, 41, 8, t->ring, 0.22f);
        if (m->kmx[i] == 1) {                                                                   /* on/off knob: a switch */
            int on1 = m->kraw[i] > 0; gfx_rrect(cx - 11, cy - 5, 22, 10, 5, on1 ? (hl ? t->ring : t->on) : t->track, 1); gfx_disc(on1 ? cx + 6 : cx - 6, cy, 3.6f, RGB(255, 255, 255), 1);
        } else {
            gfx_arc(cx, cy, 11, 3, 135, 45, t->track, 1); if (m->kv[i] > 0) gfx_arc(cx, cy, 11, 3, 135, 135 + 2.7f * m->kv[i], col, 1);
            itoa2(m->kmx[i] > 1 && m->kmx[i] <= 30 ? m->kraw[i] : m->kv[i], b); gfx_text(cx, cy, b, &FONT9, hl ? t->text : t->sub, "mm", 1); }
        gfx_text(cx, 113, m->kn[i], &FONT7, col, "mm", 1); }
    /* page dots */
    int pages = (m->nk + 3) / 4; for (int p = 0; p < pages && pages > 1; p++) gfx_disc(80 - 3 * (pages - 1) + 6 * p, 124, 1.6f, p == page ? t->ring : t->track, 1);
}
