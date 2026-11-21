#include "pages.h"
#define RGB(r, g, b) ((rgb_t){r, g, b})
static void itoa_(int v, char *s) { char t[12]; int n = 0; if (v < 0) v = 0; do { t[n++] = '0' + v % 10; v /= 10; } while (v); for (int i = 0; i < n; i++) s[i] = t[n - 1 - i]; s[n] = 0; }
static void num(char *s, int v, const char *suffix) { itoa_(v, s); while (*s) s++; while ((*s = *suffix++)) s++; }
void battery(float x, float y, int pct, int chg)
{
    const theme_t *t = gfx_theme(); gfx_rrect(x, y, 15, 8, 2.5f, t->sub, 0.85f); gfx_rrect(x + 1.5f, y + 1.5f, 12, 5, 1.3f, t->track, 1);
    float w = 12 * pct / 100.0f; if (w < 2.6f) w = 2.6f; gfx_rrect(x + 1.5f, y + 1.5f, w, 5, 1.3f, pct > 25 ? t->on : t->warn, 1); gfx_rrect(x + 15, y + 2.5f, 1.8f, 3, 0.9f, t->sub, 0.85f);
    if (chg) { rgb_t c = RGB(255, 214, 64); gfx_tri(x - 3, y - 1, x - 7.5f, y + 4.6f, x - 4.2f, y + 4.2f, c, 1); gfx_tri(x - 4.8f, y + 3.6f, x - 5.8f, y + 9.4f, x - 1.4f, y + 3.4f, c, 1); }
}
void speaker(float x, float y, rgb_t c)
{
    gfx_rrect(x, y + 3, 3, 4, 0.8f, c, 1); gfx_tri(x + 3, y + 3, x + 7, y, x + 7, y + 10, c, 1); gfx_tri(x + 3, y + 3, x + 7, y + 10, x + 3, y + 7, c, 1);
    gfx_arc(x + 8, y + 5, 3.2f, 1.2f, 310, 50, c, 1); gfx_arc(x + 8, y + 5, 5.5f, 1.2f, 310, 50, c, 0.7f);
}
/* Load slot (Apple Watch style): outer ring = DSP CPU, inner ring = audio engine; values below. -1 = unknown. */
static void ring(float cx, float cy, float r, int v, rgb_t c)
{
    const theme_t *t = gfx_theme(); gfx_arc(cx, cy, r, 2.6f, 0, 0, t->track, 1);
    if (v <= 0) return; if (v >= 100) { gfx_arc(cx, cy, r, 2.6f, 0, 0, c, 1); return; }
    float e = 270 + 3.6f * v; gfx_arc(cx, cy, r, 2.6f, 270, e, c, 1);
    gfx_disc(cx, cy - r, 1.3f, c, 1); gfx_disc(cx + r * gfx_sin(e + 90), cy + r * gfx_sin(e), 1.3f, c, 1);
}
static void load_rings(float cx, float cy, int cpu, int eng)
{   /* outer ring = DSP CPU, inner ring = audio engine; a ring turns red above 85 %. No numbers here (no room to say which
     * is which); the exact values belong on a page with space. */
    const theme_t *t = gfx_theme(); rgb_t cc = cpu > 84 ? t->warn : t->on, ec = eng > 84 ? t->warn : t->ring;
    ring(cx, cy, 8.5f, cpu, cc); ring(cx, cy, 4.8f, eng, ec);
    gfx_text(cx, 118, "LOAD", &FONT7, (cpu > 84 || eng > 84) ? t->warn : t->sub, "mm", 1);
}
void page_home(const model_t *m)
{
    const theme_t *t = gfx_theme(); char b[16]; static const char *const lab[9] = {"NR", "FX1", "DRV", "AMP", "IR", "EQ", "FX2", "DLY", "RVB"};
    gfx_bg();
    if (m->bt >= 0) { gfx_pill(3, 2, 24, 10, "BT", &FONT7, m->bt, m->bt ? t->ring : t->track); if (m->bt) gfx_disc(8, 7, 1.8f, t->on, 1); }
    if (m->vol >= 0) { speaker(31, 2, t->text); gfx_bar(43, 5, 40, 5, m->vol / 100.0f, t->ring); num(b, m->vol, ""); gfx_text(86, 7.5f, b, &FONT7, t->text, "lm", 1); }
    if (m->bat >= 0) { battery(138, 2, m->bat, m->chg); }
    /* preset row: arrow + P-pill + name, centred as one group */
    { char p[4] = "P"; p[1] = '0' + (m->preset / 10) % 10; p[2] = '0' + m->preset % 10; p[3] = 0;
      const font_t *f = gfx_text_w(&FONT16, m->name) <= 104 ? &FONT16 : &FONT12; float nw = gfx_text_w(f, m->name), sw = m->edited ? gfx_text_w(f, "*") + 2 : 0;
      float tot = 36 + 4 + nw, x0 = (160 - tot) * 0.5f; if (x0 < 2) x0 = 2; (void)sw;   /* pill + name centred; the * hangs outside */
      gfx_pill(x0, 17, 36, 18, p, &FONT12, 1, t->ring);
      gfx_text(x0 + 40, 27, m->name, f, t->text, "lm", 1); if (m->edited) gfx_text(x0 + 42 + nw, 27, "*", f, t->sub, "lm", 1); }
    gfx_tray(1, 41, 158, 43, 1, 41, 126, 84, 7, t->dark ? RGB(20, 0, 24) : t->text, t->dark ? 0.30f : 0.07f);
    for (int i = 0; i < 9; i++) {
        float x = 3 + (i % 5) * 31, y = 44 + (i / 5) * 42;
        int k = m->order[i] < 9 ? m->order[i] : i, lit = m->on[k]; gfx_tile(x, y, 26, 26, lit, k == m->sel, 5); sprite(k, x - 1, y + 0.5f, lit, k == 3 ? m->nam : 0); gfx_led(x + 23, y + 3, lit);
        gfx_text(x + 13, y + 27, (k == 3 && m->nam) ? "NAM" : lab[k], &FONT7, lit ? t->text : t->sub, "mt", lit ? 1 : 0.55f);
    }
    load_rings(143, 101, m->cpu, m->eng);
}
