#include "pages.h"
#define RGB(r, g, b) ((rgb_t){r, g, b})
/* Edit page (Berry design). Layout (160 x 128):
 *   0..12   preset + name
 *  13..42   the 9 blocks in chain order, two rows (5 + 4), name inside, the edited one ringed
 *  45..78   model card: block picture, block name, model, maker, ON/OFF badge, Basic/NAM switch
 *  81..127  controls, 4 per page (ring + value, or a green switch for on/off knobs), page dots
 * The highlighted item is what the knob changes: a knob (ksel), the model or the AMP mode (ekind). */
static const char *const LAB[9] = {"NR", "FX1", "DRV", "AMP", "IR", "EQ", "FX2", "DLY", "RVB"};
static const rgb_t GC[9] = {{40, 90, 170}, {40, 140, 80}, {200, 50, 50}, {220, 170, 60}, {70, 60, 50}, {60, 55, 70}, {190, 130, 40}, {50, 130, 220}, {140, 90, 210}};
static void itoa2(int v, char *s) { char t[12]; int n = 0; if (v < 0) v = 0; do { t[n++] = '0' + v % 10; v /= 10; } while (v); for (int i = 0; i < n; i++) s[i] = t[n - 1 - i]; s[n] = 0; }
static rgb_t dim(rgb_t c, const theme_t *t) { int l = (c.r * 3 + c.g * 6 + c.b) / 10; l = t->dark ? l * 24 / 100 + 28 : l * 28 / 100 + 112; return RGB(l, l * 9 / 10, l); }
static void ring(float x, float y, float w, float h, float r, int ed) { const theme_t *t = gfx_theme(); gfx_rring(x - 2, y - 2, w + 4, h + 4, r + 2, ed ? 2.4f : 1.6f, t->ring, 1); }
void page_edit(const model_t *m)
{
    const theme_t *t = gfx_theme(); char b[24]; int sel = m->sel < 0 ? 0 : m->sel, on = m->on[sel], k = m->ekind; float sx = 0, sy = 0;
    rgb_t trk = t->dark ? rgbf(t->bg1, RGB(10, 0, 14), 0.66f) : rgbf(t->bg1, t->text, 0.26f);        /* inactive part: dark */
    rgb_t act = t->dark ? rgbf(t->ring, RGB(255, 255, 255), 0.38f) : t->ring;                        /* active part: bright */
    int ed = m->nav == 0 || m->eopen;                                                                /* the highlighted item is being edited (else only hovered) */
    gfx_bg();
    /* header */
    b[0] = 'P'; b[1] = '0' + (m->preset / 10) % 10; b[2] = '0' + m->preset % 10; b[3] = 0;
    gfx_pill(4, 1, 24, 10, b, &FONT7, 1, t->ring); gfx_text(32, 6, m->name, &FONT9, t->text, "lm", 1);
    if (m->edited) gfx_text(32 + gfx_text_w(&FONT9, m->name) + 2, 6, "*", &FONT9, t->sub, "lm", 1);
    /* chain: 2 rows of wide tiles */
    for (int j = 0; j < 9; j++) { int i = m->order[j] < 9 ? m->order[j] : j, o = m->on[i]; float x = 4 + (j % 5) * 31, y = 13 + (j / 5) * 16; rgb_t c = o ? GC[i] : dim(GC[i], t);
        if (i == sel) { sx = x; sy = y; }
        gfx_rrect(x, y, 28, 13, 4, c, 1); if (o) gfx_rrect(x + 1, y + 1, 26, 5, 3, RGB(255, 255, 255), 0.18f);
        gfx_text(x + 14, y + 7, LAB[i], &FONT9, o ? RGB(255, 255, 255) : (t->dark ? RGB(165, 140, 168) : RGB(236, 230, 236)), "mm", 1); }
    if (m->rgx > 0) { sx = m->rgx; sy = m->rgy; }
    gfx_rring(sx - 2.5f, sy - 2.5f, 33, 18, 6.5f, 2, t->ring, 1);
    /* model card (slim: the freed rows go to the controls) */
    gfx_rrect(4, 45, 152, 33, 7, t->dark ? RGB(20, 0, 24) : t->text, t->dark ? 0.30f : 0.07f);
    gfx_tile(8, 48, 26, 26, on, 0, 6); sprite(sel, 7, 48.5f, on, sel == 3 ? m->nam : 0);
    int ms = k == 2 && ed;                                                                         /* model box selected and being edited: solid */
    if (k == 2) { if (ms) gfx_rrect(46, 46, 72, 31, 6, t->ring, 1); else gfx_rring(45.5f, 45.5f, 73, 32, 6.5f, 1.5f, t->ring, 1); }
    gfx_text(50, 50, LAB[sel], &FONT7, ms ? t->ink : t->sub, "lm", 1);
    { const font_t *nf = gfx_text_w(&FONT16, m->mname) <= 66 ? &FONT16 : gfx_text_w(&FONT14, m->mname) <= 66 ? &FONT14 : &FONT11; gfx_text(50, 60.5f, m->mname, nf, ms ? t->ink : t->text, "lm", 1); }
    if (m->brand[0]) gfx_text(50, 71.5f, m->brand, &FONT7, ms ? t->ink : t->sub, "lm", 1);
    gfx_pill(122, 48, 30, 13, on ? "ON" : "OFF", &FONT9, on, on ? t->on : t->track);
    if (m->pulse > 0) gfx_rring(122 - 2.2f * m->pulse, 48 - 2.2f * m->pulse, 30 + 4.4f * m->pulse, 13 + 4.4f * m->pulse, 6.5f + 2.2f * m->pulse, 1.8f, on ? t->on : t->sub, 0.9f - 0.27f * m->pulse);
    if (sel == 3) { if (k == 3) ring(118, 63, 34, 12, 6, ed);
        gfx_rrect(118, 63, 34, 12, 6, trk, 1); gfx_rrect(m->nam ? 135 : 119, 64, 16, 10, 5, act, 1);
        gfx_text(127, 69, "B", &FONT7, m->nam ? t->sub : t->ink, "mm", 1); gfx_text(143, 69, "N", &FONT7, m->nam ? t->ink : t->sub, "mm", 1); }
    /* controls: 4 per page, taller rings, bigger numbers and names; on/off knobs are switches (green when on) */
    int page = (k == 0 && m->ksel > 0) ? m->ksel / 4 : 0, n = m->nk - page * 4; if (n > 4) n = 4;
    if (k == 0 && m->ksel >= page * 4 && m->ksel < page * 4 + 4) { float hx = (m->hlx > 0 ? m->hlx : 22 + 39 * (m->ksel - page * 4)) - 18;
        if (ed) gfx_rrect(hx, 81, 36, 40, 8, t->ring, 1); else gfx_rring(hx, 81, 36, 40, 8, 1.6f, t->ring, 1); }       /* selected + editing: solid; selected only: outline */
    for (int c = 0; c < n; c++) { int i = page * 4 + c, hl = k == 0 && i == m->ksel, sold = hl && ed; float cx = 22 + 39 * c, cy = 98;
        rgb_t tk = sold ? rgbf(t->ring, RGB(0, 0, 0), 0.4f) : trk, fl = sold ? t->ink : act, tx = sold ? t->ink : hl ? t->text : t->sub;
        if (m->kmx[i] == 1) {
            int on1 = m->kraw[i] > 0; gfx_rrect(cx - 13, cy - 6, 26, 12, 6, on1 ? t->on : tk, 1); gfx_disc(on1 ? cx + 7 : cx - 7, cy, 4.4f, RGB(255, 255, 255), 1);
        } else {
            int v = m->kmx[i] > 1 && m->kmx[i] <= 30 ? m->kraw[i] : m->kv[i];
            gfx_arc(cx, cy, 12, 4, 135, 45, tk, 1); if (m->kv[i] > 0) gfx_arc(cx, cy, 12, 4, 135, 135 + 2.7f * m->kv[i], fl, 1);
            itoa2(v, b); gfx_text(cx, cy, b, v > 99 ? &FONT9 : &FONT12, tx, "mm", 1); }
        gfx_text(cx, 114, m->kn[i], &FONT8, sold ? t->ink : t->text, "mm", hl ? 1 : 0.78f); }
    /* page dots */
    int pages = (m->nk + 3) / 4; for (int p = 0; p < pages && pages > 1; p++) gfx_disc(80 - 3.5f * (pages - 1) + 7 * p, 124.5f, p == page ? 2.4f : 1.7f, p == page ? act : trk, 1);
}
