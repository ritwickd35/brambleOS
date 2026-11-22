#include "pages.h"
#define RGB(r, g, b) ((rgb_t){r, g, b})
static char *itoa4(int v, char *s) { char t[12]; int n = 0; if (v < 0) v = 0; do { t[n++] = '0' + v % 10; v /= 10; } while (v); for (int i = 0; i < n; i++) s[i] = t[n - 1 - i]; s[n] = 0; return s + n; }
static void card(float x, float y, float w, float h, int sel)
{
    const theme_t *t = gfx_theme(); if (sel) gfx_rring(x - 2, y - 2, w + 4, h + 4, 9, 2.2f, t->ring, 1);
    gfx_rrect(x, y, w, h, 7, t->dark ? RGB(20, 0, 24) : t->text, t->dark ? 0.30f : 0.07f);
}
static void header(const char *title)
{
    const theme_t *t = gfx_theme(); gfx_text(6, 7, title, &FONT9, t->text, "lm", 1);
}
/* Recording / looper: big state disc + time, Pre/Post, two level bars, transport (rec/play, stop/clear) */
void page_rec(const model_t *m)
{
    const theme_t *t = gfx_theme(); char b[16], *p; gfx_bg(); header("Looper");
    card(4, 16, 76, 46, 0);
    rgb_t sc = m->rstate == 1 ? t->warn : m->rstate == 2 ? t->on : t->sub;
    gfx_arc(26, 39, 14, 3, 0, 0, t->track, 1); if (m->rstate == 1 || m->rstate == 2) gfx_arc(26, 39, 14, 3, 270, 270 + (m->rtime10 % 100) * 3.6f, sc, 1);
    gfx_disc(26, 39, 7, sc, 1); gfx_disc(24, 37, 2.5f, RGB(255, 255, 255), 0.3f);
    p = itoa4(m->rtime10 / 10, b); *p++ = '.'; *p++ = '0' + m->rtime10 % 10; *p++ = 's'; *p = 0; gfx_text(46, 33, b, &FONT12, t->text, "lm", 1);
    gfx_text(46, 49, m->rstate == 0 ? "Empty" : m->rstate == 1 ? "Recording" : m->rstate == 2 ? "Playing" : "Stopped", &FONT7, t->sub, "lm", 1);
    gfx_rrect(86, 20, 68, 18, 9, t->track, 1); gfx_rrect(m->rpost ? 120 : 88, 22, 32, 14, 7, t->ring, 1);
    gfx_text(104, 29, "Pre", &FONT8, m->rpost ? t->sub : t->ink, "mm", 1); gfx_text(136, 29, "Post", &FONT8, m->rpost ? t->ink : t->sub, "mm", 1);
    gfx_text(6, 70, "REC", &FONT7, t->text, "lm", 1); itoa4(m->rvol, b); gfx_text(78, 70, b, &FONT7, t->sub, "rm", 1); gfx_bar(6, 78, 72, 5, m->rvol / 100.0f, t->ring);
    gfx_text(84, 70, "PLAY", &FONT7, t->text, "lm", 1); itoa4(m->pvol, b); gfx_text(154, 70, b, &FONT7, t->sub, "rm", 1); gfx_bar(84, 78, 70, 5, m->pvol / 100.0f, t->on);
    card(4, 92, 74, 30, m->rsel == 0); gfx_disc(28, 107, 6, t->warn, 1); gfx_text(41, 107, "/", &FONT12, t->sub, "mm", 1); gfx_tri(49, 101, 49, 113, 58, 107, t->text, 1);
    card(82, 92, 74, 30, m->rsel == 1); gfx_rrect(100, 101, 12, 12, 2.5f, t->text, 0.9f); gfx_text(122, 107, "/", &FONT12, t->sub, "mm", 1); gfx_text(136, 107, "x", &FONT12, t->sub, "mm", 1);
}
/* Drum machine: play disc with beat rings, type / volume / BPM, four item cards */
void page_drum(const model_t *m)
{
    const theme_t *t = gfx_theme(); char b[8]; gfx_bg(); header("Drums");
    card(4, 16, 60, 52, 0);
    for (int k = 0; k < 3 && m->dplay; k++) gfx_arc(34, 42, 18 + 3 * k, 2, 0, 0, t->ring, 0.25f - 0.07f * k);
    gfx_disc(34, 42, 15, m->dplay ? t->ring : t->tile, 1);
    if (m->dplay) { gfx_rrect(28, 36, 4, 12, 1, t->ink, 1); gfx_rrect(36, 36, 4, 12, 1, t->ink, 1); } else gfx_tri(30, 35, 30, 49, 42, 42, t->text, 1);
    gfx_text(70, 22, "Type", &FONT7, t->sub, "lm", 1); gfx_text(154, 22, m->dtype, &FONT9, t->text, "rm", 1);
    gfx_text(70, 36, "VOL", &FONT7, t->sub, "lm", 1); gfx_bar(90, 34, 64, 5, m->dvol / 100.0f, t->ring);
    gfx_text(70, 56, "BPM", &FONT7, t->sub, "lm", 1); itoa4(m->bpm, b); gfx_text(154, 54, b, &FONT16, t->text, "rm", 1);
    static const char *const nm[4] = {"Play", "Type", "VOL", "BPM"};
    for (int i = 0; i < 4; i++) { float x = 4 + i * 39; int s = m->dsel == i; rgb_t c = s ? t->text : t->sub; card(x, 76, 35, 34, s);
        float cx = x + 17.5f, cy = 90;
        if (i == 0) { gfx_tri(cx - 7, cy - 5, cx - 7, cy + 5, cx, cy, c, 1); gfx_rrect(cx + 2, cy - 4, 7, 8, 1.5f, c, 1); }
        else if (i == 1) for (int k = 0; k < 3; k++) gfx_rrect(cx - 7, cy - 5 + 4.5f * k, 14, 2, 1, c, 1);
        else if (i == 2) { gfx_rrect(cx - 7, cy - 2, 3, 4, 0.8f, c, 1); gfx_tri(cx - 4, cy - 2, cx, cy - 5, cx, cy + 5, c, 1); gfx_tri(cx - 4, cy - 2, cx, cy + 5, cx - 4, cy + 2, c, 1); gfx_arc(cx + 1, cy, 4, 1.2f, 310, 50, c, 1); }
        else { gfx_tri(cx - 6, cy + 6, cx - 2, cy - 6, cx + 2, cy - 6, c, 0.9f); gfx_tri(cx - 6, cy + 6, cx + 2, cy - 6, cx + 6, cy + 6, c, 0.9f); }
        gfx_text(cx, 104, nm[i], &FONT7, c, "mm", 1); }
}
/* Settings: title + page number, up to 5 rows (text value, bar, or switch), tab strip at the bottom */
void page_settings(const model_t *m)
{
    const theme_t *t = gfx_theme(); char b[8], *p; gfx_bg();
    gfx_arc(9, 8, 4, 1.6f, 0, 0, t->sub, 1); gfx_disc(9, 8, 1.3f, t->sub, 1); gfx_text(18, 8, m->stitle, &FONT9, t->text, "lm", 1);
    if (m->spages > 1) { p = itoa4(m->spage, b); *p++ = '/'; itoa4(m->spages, p); gfx_text(154, 8, b, &FONT7, t->sub, "rm", 1); }
    for (int i = 0; i < m->sn && i < 5; i++) { float y = 18 + i * 17; int s = i == m->ssel;
        card(4, y, 152, 15, s); gfx_text(12, y + 7.5f, m->slab[i], &FONT8, t->text, "lm", 1);
        if (m->skind[i] == 1) { gfx_bar(84, y + 5, 52, 5, m->snum[i] / 100.0f, t->ring); itoa4(m->snum[i], b); gfx_text(150, y + 7.5f, b, &FONT7, t->sub, "rm", 1); }
        else if (m->skind[i] == 2) { int on = m->snum[i]; gfx_rrect(124, y + 2.5f, 26, 10, 5, on ? t->on : t->track, 1); gfx_disc(on ? 145 : 129, y + 7.5f, 3.6f, RGB(255, 255, 255), 1); }
        else gfx_text(148, y + 7.5f, m->sval[i], &FONT8, s ? t->text : t->sub, "rm", 1); }
    /* tab strip */
    for (int i = 0; i < 5 && m->tabs[i]; i++) { float x = 2 + i * 31.6f; int s = i == m->tsel;
        if (s) gfx_rrect(x, 108, 30, 16, 6, t->ring, 1);
        gfx_text(x + 15, 116, m->tabs[i], &FONT8, s ? t->ink : t->sub, "mm", 1); }
}
/* Save dialog over a dimmed page */
void page_dialog(const model_t *m)
{
    const theme_t *t = gfx_theme(); char b[24]; page_home(m); gfx_rrect(-2, -2, 164, 132, 0, t->bg1, 0.62f);
    gfx_rrect(14, 28, 132, 72, 9, t->tile, 1); gfx_rrect(15, 29, 130, 30, 8, t->hi, t->dark ? 0.08f : 0.4f);
    gfx_text(80, 42, "Save changes?", &FONT12, t->text, "mm", 1);
    b[0] = 'P'; b[1] = '0' + (m->preset / 10) % 10; b[2] = '0' + m->preset % 10; b[3] = ' '; b[4] = ' '; { int i = 0; for (; m->name[i] && i < 16; i++) b[5 + i] = m->name[i]; b[5 + i] = 0; }
    gfx_text(80, 57, b, &FONT8, t->sub, "mm", 1);
    if (m->ssel == 0) gfx_rring(24, 70, 56, 22, 11, 2.2f, t->ring, 1); else gfx_rring(80, 70, 56, 22, 11, 2.2f, t->ring, 1);
    gfx_pill(26, 72, 52, 18, "Save", &FONT9, 1, t->on); gfx_pill(82, 72, 52, 18, "Discard", &FONT9, 0, t->track);
}
