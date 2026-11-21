#include "pages.h"
#define RGB(r, g, b) ((rgb_t){r, g, b})
static const char *const NOTE[12] = {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"};
static char *itoa3(int v, char *s) { char t[12]; int n = 0; if (v < 0) v = -v; do { t[n++] = '0' + v % 10; v /= 10; } while (v); for (int i = 0; i < n; i++) s[i] = t[n - 1 - i]; s[n] = 0; return s + n; }
void page_tuner(const model_t *m)
{
    const theme_t *t = gfx_theme(); char b[20], *p; int sig = m->note >= 0, c = m->cents < -50 ? -50 : m->cents > 50 ? 50 : m->cents, intune = sig && c >= -3 && c <= 3;
    rgb_t acc = intune ? t->on : t->ring;
    gfx_bg();
    p = b; *p++ = 'A'; *p++ = '4'; *p++ = ' '; *p++ = '='; *p++ = ' '; p = itoa3(m->a4, p); *p++ = ' '; *p++ = 'H'; *p++ = 'z'; *p = 0;
    gfx_text(80, 8, b, &FONT9, t->sub, "mm", 1);
    if (m->mute) gfx_pill(118, 2, 38, 12, "MUTE", &FONT7, 1, t->warn);
    /* note, octave, frequency, cents (top); gauge arc of tick dots below, pivot off-screen, needle = bright dot + stem */
    if (sig) { gfx_text(80, 34, NOTE[m->note], &FONT24, intune ? t->on : t->text, "mm", 1);
        itoa3(m->octave, b); gfx_text(80 + gfx_text_w(&FONT24, NOTE[m->note]) * 0.5f + 3, 27, b, &FONT9, t->sub, "lm", 1);
        p = itoa3(m->hz10 / 10, b); *p++ = '.'; *p++ = '0' + m->hz10 % 10; *p++ = ' '; *p++ = 'H'; *p++ = 'z'; *p = 0; gfx_text(80, 54, b, &FONT7, t->sub, "mm", 1); }
    else gfx_text(80, 36, "play a string", &FONT9, t->sub, "mm", 1);
    for (int i = -5; i <= 5; i++) { float a = -90 + i * 10; gfx_disc(80 + 62 * gfx_sin(a + 90), 136 + 62 * gfx_sin(a), i ? 1.9f : 2.8f, i ? t->sub : acc, i ? 0.6f : 0.95f); }
    if (sig) { float a = -90 + c * 1.0f; for (int r = 34; r <= 56; r += 2) gfx_disc(80 + r * gfx_sin(a + 90), 136 + r * gfx_sin(a), 1.1f, acc, 0.25f + 0.012f * r);
        gfx_disc(80 + 62 * gfx_sin(a + 90), 136 + 62 * gfx_sin(a), 3.6f, acc, 1);
        p = b; *p++ = c > 0 ? '+' : c < 0 ? '-' : ' '; p = itoa3(c, p); *p++ = ' '; *p++ = 'c'; *p = 0; gfx_text(80, 110, intune ? "in tune" : b, &FONT9, acc, "mm", 1);
        gfx_tri(12, 92, 12, 106, 5, 99, t->sub, c < -3 ? 0.9f : 0.3f); gfx_tri(148, 92, 148, 106, 155, 99, t->sub, c > 3 ? 0.9f : 0.3f); }
}
