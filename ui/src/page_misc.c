#include "pages.h"
#define RGB(r, g, b) ((rgb_t){r, g, b})
/* Settings, Looper and Drums in the Berry design.
 * Every selectable thing has the same three looks (and works in both navigation modes):
 *   1 not selected: plain card        2 selected: thin accent outline        3 selected and being edited: solid accent, dark text
 * Controls: list (< name >), level bar (dark track, bright fill, value), on/off switch (green when on). */
static char *itoa4(int v, char *s) { char t[12]; int n = 0; if (v < 0) { *s++ = '-'; v = -v; } do { t[n++] = '0' + v % 10; v /= 10; } while (v); for (int i = 0; i < n; i++) s[i] = t[n - 1 - i]; s[n] = 0; return s + n; }
static rgb_t trk(const theme_t *t) { return t->dark ? rgbf(t->bg1, RGB(10, 0, 14), 0.66f) : rgbf(t->bg1, t->text, 0.26f); }
static rgb_t act(const theme_t *t) { return t->dark ? rgbf(t->ring, RGB(255, 255, 255), 0.38f) : t->ring; }
static int editing(const model_t *m) { return m->nav == 0 || m->eopen; }
static int st(const model_t *m, int sel, int i) { return sel != i ? 0 : editing(m) ? 2 : 1; }          /* UX state of item i when item `sel` is selected */
static void card(float x, float y, float w, float h, float r, int s)
{
    const theme_t *t = gfx_theme();
    if (s == 2) { gfx_rrect(x, y, w, h, r, t->ring, 1); return; }
    gfx_rrect(x, y, w, h, r, t->dark ? RGB(20, 0, 24) : t->text, t->dark ? 0.30f : 0.07f);
    if (s == 1) gfx_rring(x - 0.5f, y - 0.5f, w + 1, h + 1, r + 0.5f, 1.7f, t->ring, 1);
}
static void head(const char *title, const model_t *m)
{
    const theme_t *t = gfx_theme(); char b[8], *p;
    gfx_text(6, 7, title, &FONT9, t->text, "lm", 1);
    if (m->spages > 1) for (int i = 0; i < m->spages; i++) gfx_disc(152 - 6 * (m->spages - 1 - i), 7, i == m->spage - 1 ? 2.3f : 1.7f, i == m->spage - 1 ? act(t) : trk(t), 1);
    (void)b; (void)p;
}
static void bar(float x, float y, float w, float h, int v, int s)                                    /* level bar, 0..100 */
{
    const theme_t *t = gfx_theme(); rgb_t tk = s == 2 ? rgbf(t->ring, RGB(255, 255, 255), 0.5f) : trk(t), fl = s == 2 ? t->ink : act(t);
    gfx_rrect(x, y, w, h, h / 2, tk, 1); if (v > 0) { float fw = w * v / 100.0f; if (fw < h) fw = h; gfx_rrect(x, y, fw, h, h / 2, fl, 1); }
}
static void sw(float x, float y, int on, int s)                                                       /* on/off switch, green when on */
{
    const theme_t *t = gfx_theme(); gfx_rrect(x, y, 26, 12, 6, on ? t->on : (s == 2 ? rgbf(t->ring, RGB(255, 255, 255), 0.5f) : trk(t)), 1); gfx_disc(on ? x + 19 : x + 7, y + 6, 4.4f, RGB(255, 255, 255), 1);
}

/* ---- Settings: title + page dots, a list of rows, a live preview, the tab strip ---- */
void page_settings(const model_t *m)
{
    const theme_t *t = gfx_theme(); char b[16]; gfx_bg(); head(m->stitle, m);
    for (int i = 0; i < m->sn && i < 5; i++) { float y = 16 + i * 17; int s = st(m, m->ssel, i); rgb_t tx = s == 2 ? t->ink : t->text;
        card(4, y, 152, 15, 7, s); gfx_text(11, y + 7.5f, m->slab[i], &FONT8, tx, "lm", 1);
        if (m->skind[i] == 0) {                                                                       /* list: < value > */
            float w = gfx_text_w(&FONT11, m->sval[i]); gfx_text(146 - 8, y + 7.5f, m->sval[i], &FONT11, tx, "rm", 1);
            rgb_t ar = s == 2 ? t->ink : t->sub; gfx_tri(142 + 6, y + 4.5f, 142 + 6, y + 10.5f, 146 + 6, y + 7.5f, ar, 1); gfx_tri(146 - 8 - w - 4, y + 4.5f, 146 - 8 - w - 4, y + 10.5f, 146 - 8 - w - 8, y + 7.5f, ar, 1);
        } else if (m->skind[i] == 1) { bar(80, y + 5, 54, 5, m->snum[i], s); itoa4(m->snum[i], b); gfx_text(150, y + 7.5f, b, &FONT8, tx, "rm", 1); }
        else if (m->skind[i] == 2) sw(124, y + 1.5f, m->snum[i], s);
        else { bar(80, y + 5, 40, 5, m->snum[i], s); gfx_text(150, y + 7.5f, m->sval[i], &FONT8, tx, "rm", 1); } }          /* 3: bar with a text value (dB) */
    int py = 16 + m->sn * 17 + 3;                                                                     /* live preview */
    if (m->spreview == 1) {                                                                           /* theme swatches */
        static const rgb_t A[6] = {{164, 104, 166}, {244, 234, 216}, {190, 70, 80}, {50, 70, 120}, {120, 80, 180}, {232, 214, 190}}, B[6] = {{221, 168, 239}, {206, 102, 16}, {250, 190, 190}, {170, 200, 250}, {200, 170, 250}, {120, 100, 90}};
        card(4, py, 152, 108 - py - 3, 7, 0);
        for (int i = 0; i < 6; i++) { float cx = 17 + i * 25.2f, cy = py + (108 - py - 3) / 2.0f; gfx_disc(cx, cy, 8.5f, A[i], 1); gfx_disc(cx + 2.5f, cy + 2.5f, 4.6f, B[i], 1);
            if (i == m->slevel) gfx_rring(cx - 11, cy - 11, 22, 22, 11, 2.2f, t->ring, 1); }
    } else if (m->spreview == 2) {                                                                    /* live input meter with clip mark */
        card(4, py, 152, 108 - py - 3, 7, 0); float mh = 108 - py - 3, cy = py + mh / 2;
        for (int i = 0; i < 24; i++) { float x = 11 + i * 5.8f; int on = i * 100 / 24 < m->slevel; rgb_t c = i < 16 ? t->on : i < 21 ? RGB(235, 190, 60) : t->warn;
            gfx_rrect(x, cy - 5, 4.4f, 10, 1.6f, on ? c : trk(t), 1); }
        gfx_text(80, py + mh - 6, "play hard: aim for the amber zone", &FONT7, t->sub, "mm", 1);
    }
    for (int i = 0; i < 5 && m->tabs[i]; i++) { float x = 3 + i * 30.8f; int s = i == m->tsel;                  /* tab strip */
        if (s) gfx_rrect(x, 110, 29, 15, 7, t->ring, 1);
        gfx_text(x + 14.5f, 117.5f, m->tabs[i], &FONT8, s ? t->ink : t->text, "mm", s ? 1 : 0.8f); }
}

/* ---- Looper ---- */
void page_rec(const model_t *m)
{
    const theme_t *t = gfx_theme(); char b[16], *p; gfx_bg(); gfx_text(6, 7, "Looper", &FONT9, t->text, "lm", 1);
    rgb_t sc = m->rstate == 1 ? t->warn : m->rstate == 2 ? t->on : t->sub;
    { const char *sn = m->rstate == 0 ? "EMPTY" : m->rstate == 1 ? "REC" : m->rstate == 2 ? "PLAY" : "STOP"; float w = gfx_text_w(&FONT8, sn) + 14;
      gfx_rrect(156 - w, 2, w, 11, 5.5f, trk(t), 1); gfx_disc(156 - w + 6, 7.5f, 2.6f, sc, 1); gfx_text(156 - w + 11, 7.8f, sn, &FONT8, t->text, "lm", 1); }
    card(4, 17, 76, 42, 7, 0);                                                                        /* state disc + time */
    gfx_arc(26, 38, 14, 4, 0, 0, trk(t), 1); if (m->rstate == 1 || m->rstate == 2) gfx_arc(26, 38, 14, 4, 270, 270 + (m->rtime10 % 100) * 3.6f, sc, 1);
    gfx_disc(26, 38, 7, sc, 1); gfx_disc(24, 36, 2.4f, RGB(255, 255, 255), 0.3f);
    p = itoa4(m->rtime10 / 10, b); *p++ = '.'; *p++ = '0' + m->rtime10 % 10; *p++ = 's'; *p = 0; gfx_text(46, 33, b, &FONT14, t->text, "lm", 1);
    gfx_text(46, 48, "of 60 s", &FONT7, t->sub, "lm", 1);
    { int s = st(m, m->rsel, 0); card(86, 17, 70, 42, 7, s); rgb_t tx = s == 2 ? t->ink : t->text;                  /* Pre / Post */
      gfx_text(121, 26, "Record", &FONT7, s == 2 ? t->ink : t->sub, "mm", 1);
      gfx_rrect(92, 33, 58, 17, 8.5f, s == 2 ? rgbf(t->ring, RGB(0, 0, 0), 0.4f) : trk(t), 1); gfx_rrect(m->rpost ? 121 : 93, 34, 28, 15, 7.5f, s == 2 ? t->ink : act(t), 1);
      gfx_text(107, 41.5f, "Pre", &FONT8, m->rpost ? tx : (s == 2 ? t->ring : t->ink), "mm", 1); gfx_text(136, 41.5f, "Post", &FONT8, m->rpost ? (s == 2 ? t->ring : t->ink) : tx, "mm", 1); }
    for (int i = 0; i < 2; i++) { float y = 64 + i * 16; int s = st(m, m->rsel, 1 + i); int v = i ? m->pvol : m->rvol; rgb_t tx = s == 2 ? t->ink : t->text;
        card(4, y, 152, 14, 7, s); gfx_text(11, y + 7, i ? "PLAY" : "REC", &FONT8, tx, "lm", 1); bar(44, y + 4.5f, 84, 5, v, s); itoa4(v, b); gfx_text(150, y + 7, b, &FONT8, tx, "rm", 1); }
    for (int i = 0; i < 2; i++) { float x = 4 + i * 78; int s = st(m, m->rsel, 3 + i); rgb_t c = s == 2 ? t->ink : t->text, d = s == 2 ? t->ink : t->sub;
        card(x, 98, 74, 28, 8, s);
        if (i == 0) { gfx_disc(x + 23, 112, 6, s == 2 ? t->ink : t->warn, 1); gfx_text(x + 38, 112, "/", &FONT12, d, "mm", 1); gfx_tri(x + 46, 106, x + 46, 118, x + 55, 112, c, 1); }
        else { gfx_rrect(x + 17, 106, 12, 12, 2.5f, c, 1); gfx_text(x + 40, 112, "/", &FONT12, d, "mm", 1); gfx_text(x + 54, 112, "x", &FONT12, d, "mm", 1); } }
}

/* ---- Drums ---- */
void page_drum(const model_t *m)
{
    const theme_t *t = gfx_theme(); char b[8]; gfx_bg(); gfx_text(6, 7, "Drums", &FONT9, t->text, "lm", 1);
    { int on = m->dplay; float w = gfx_text_w(&FONT8, on ? "PLAYING" : "STOPPED") + 14; gfx_rrect(156 - w, 2, w, 11, 5.5f, trk(t), 1); gfx_disc(156 - w + 6, 7.5f, 2.6f, on ? t->on : t->sub, 1);
      gfx_text(156 - w + 11, 7.8f, on ? "PLAYING" : "STOPPED", &FONT8, t->text, "lm", 1); }
    { int s = st(m, m->dsel, 0); card(4, 17, 58, 62, 8, s); rgb_t c = s == 2 ? t->ink : t->text;                          /* play / stop */
      for (int k = 0; k < 3 && m->dplay; k++) gfx_arc(33, 46, 19 + 3 * k, 2, 0, 0, s == 2 ? t->ink : t->ring, 0.30f - 0.09f * k);
      gfx_disc(33, 46, 15, s == 2 ? rgbf(t->ring, RGB(0, 0, 0), 0.4f) : (m->dplay ? t->ring : trk(t)), 1);
      if (m->dplay) { gfx_rrect(27, 40, 4.4f, 12, 1, s == 2 ? t->ink : t->ink, 1); gfx_rrect(35, 40, 4.4f, 12, 1, t->ink, 1); } else gfx_tri(29, 39, 29, 53, 41, 46, c, 1); }
    for (int i = 0; i < 3; i++) { float y = 17 + i * 21 + (i == 2 ? 0 : 0); float h = i == 2 ? 20 : 19; y = i == 0 ? 17 : i == 1 ? 38 : 59; int s = st(m, m->dsel, 1 + i); rgb_t tx = s == 2 ? t->ink : t->text, sb = s == 2 ? t->ink : t->sub;
        card(66, y, 90, h, 7, s); gfx_text(72, y + h / 2, i == 0 ? "Type" : i == 1 ? "VOL" : "BPM", &FONT8, sb, "lm", 1);
        if (i == 0) { gfx_text(124, y + h / 2, m->dtype, &FONT11, tx, "mm", 1); gfx_tri(98, y + 6.5f, 98, y + 12.5f, 94, y + 9.5f, sb, 1); gfx_tri(150, y + 6.5f, 150, y + 12.5f, 154, y + 9.5f, sb, 1); }
        else if (i == 1) { bar(94, y + 7, 46, 5, m->dvol, s); itoa4(m->dvol, b); gfx_text(150, y + h / 2, b, &FONT8, tx, "rm", 1); }
        else { itoa4(m->bpm, b); gfx_text(147, y + h / 2, b, &FONT16, tx, "rm", 1); } }
    for (int i = 0; i < 4; i++) { float x = 4 + i * 38.7f; int cur = i == (m->dplay ? m->rtime10 % 4 : -1);                                  /* beat pads */
        gfx_rrect(x, 90, 34.5f, 34, 7, cur ? act(t) : trk(t), 1); if (cur) gfx_rrect(x + 1, 91, 32.5f, 12, 6, RGB(255, 255, 255), 0.22f);
        itoa4(i + 1, b); gfx_text(x + 17, 107, b, &FONT12, cur ? t->ink : t->sub, "mm", 1); }
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
    gfx_pill(26, 72, 52, 18, "Save", &FONT9, 1, t->on); gfx_pill(82, 72, 52, 18, "Discard", &FONT9, 0, trk(t));
}
