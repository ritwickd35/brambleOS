/* ui7: replaces the home screen (window 2) with the Berry home page; other windows keep the stock picture plus a small
 * "w<id> t<theme>" tag. Reads the preset model straight from MCU RAM (M = 0x2000CEE4). No RAM of our own. */
#include "gfx.h"
#include "pages.h"
void *gfx_bind(void *c);
typedef void (*flush_fn)(int, int, int, int, u16 *);
#define FLUSH ((flush_fn)0x50BE8)
#define MALLOC ((void *(*)(unsigned))0x68D38)
#define FREE ((void (*)(void *))0x68D64)
#define SH 16                                              /* strip height: 160 x 16 x 2 = 5 KB, freed after every repaint */
#define WIN (*(volatile unsigned char *)0x200045A1u)
#define THEME (*(volatile unsigned char *)0x2001BB88u)
#define M ((volatile unsigned char *)0x2000CEE4u)

static void read_model(model_t *m)
{
    unsigned en = M[0x5F] | (M[0x60] << 8) | (M[0x61] << 16) | ((unsigned)M[0x62] << 24); int i;
    m->preset = (M[8] | (M[9] << 8)) + 1; m->edited = 0; m->vol = m->bt = m->bat = m->cpu = m->eng = m->bpm = -1; m->chg = 0;
    for (i = 0; i < 23 && M[0x51 + i] >= 32 && M[0x51 + i] < 127; i++) m->name[i] = M[0x51 + i];
    m->name[i] = 0;
    for (i = 0; i < 9; i++) m->on[i] = (en >> i) & 1;
    m->nam = (en >> 3) & (en >> 9) & 1; m->sel = -1;
    if (*(volatile unsigned char *)0x2001BBB4u) { int v = (*(volatile unsigned short *)0x2001BBB2u + 5) / 10; m->cpu = v > 199 ? 199 : v; }   /* CFW CPU meter, 0.1 % units */
}

__attribute__((section(".text.hook"))) void ui_hook(int x1, int x2, int y1, int y2, u16 *px)
{
    long long ctxbuf[4]; void *old = gfx_bind(ctxbuf);
    if (WIN == 2) {
        /* The stock code flushes only the areas its own widgets changed, laid out differently from ours. Repaint, full
         * width, every band of our layout (header, preset row, block row 1, block row 2 + load) that the area touches. */
        static const unsigned char zs[4] = {0, 14, 39, 85}, ze[4] = {13, 38, 84, 127};
        model_t m; u16 *buf; int z0 = 0, z1 = 3, y;
        int ys, ye;
        while (z0 < 3 && y1 > ze[z0]) z0++; while (z1 > 0 && y2 < zs[z1]) z1--;
        /* Header and preset row: whole band (the stock name label sits elsewhere). Block rows: only the flushed rows,
         * full width - the stock code walks every changed icon top to bottom, so all rows get refreshed once. */
        ys = z0 <= 1 ? zs[z0] : y1; ye = z1 <= 1 ? ze[z1] : y2;
        read_model(&m); buf = (u16 *)MALLOC(160 * SH * 2);
        if (buf) {
            for (y = ys; y <= ye; y += SH) { int e = y + SH - 1 > ye ? ye : y + SH - 1;
                gfx_begin(0, 159, y, e, buf, &THEMES[0]); page_home(&m); FLUSH(0, 159, y, e, buf); }
            FREE(buf); gfx_bind(old); return;
        }
        gfx_begin(x1, x2, y1, y2, px, &THEMES[0]); page_home(&m);
    } else if (x1 <= 40 && y1 <= 12) {
        char s[8]; unsigned w = WIN, t = THEME; int n = 0;
        s[n++] = 'w'; if (w >= 10) s[n++] = '0' + (w / 10) % 10; s[n++] = '0' + w % 10; s[n++] = ' '; s[n++] = 't'; s[n++] = '0' + t % 10; s[n] = 0;
        gfx_begin(x1, x2, y1, y2, px, &THEMES[0]);
        gfx_rrect(0, 0, 36, 11, 3, (rgb_t){0, 0, 0}, 0.75f); gfx_text(18, 5.5f, s, &FONT7, (rgb_t){255, 255, 255}, "mm", 1);
    }
    gfx_bind(old);
    FLUSH(x1, x2, y1, y2, px);
}
