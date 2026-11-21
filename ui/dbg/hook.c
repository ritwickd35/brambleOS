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
    { int n = 0, k; for (i = 0; i < 10 && n < 9; i++) { k = M[0x63 + i]; if (k < 9) m->order[n++] = k; }    /* chain order (getter 0x50280) */
      if (n != 9) for (i = 0; i < 9; i++) m->order[i] = i; }
    m->nam = (en >> 3) & (en >> 9) & 1; m->sel = -1;
    { unsigned lv = *(volatile unsigned char *)0x200084A9u; m->bat = (lv > 5 ? 5 : lv) * 20; }               /* battery level 0..5 (getter 0x14800) */
    m->chg = *(volatile unsigned char *)0x200084ACu == 2;                                                      /* 2 = USB power in */
    m->edited = *(volatile unsigned char *)0x2000D134u != 0;                                                   /* unsaved changes (stock draws its '*' from this) */
    if (*(volatile unsigned char *)0x2001BBB4u) { int v = (*(volatile unsigned short *)0x2001BBB2u + 5) / 10; m->cpu = v > 199 ? 199 : v; }   /* CFW CPU meter, 0.1 % units */
}

/* DEBUG: bytes +0x20..+0x2F of the window data block the window manager passes to every window callback (gp-20216) */
static void dbg_win(void)
{
    const volatile unsigned char *w = (const volatile unsigned char *)0x2000AB28u; char s[64]; int n = 0, i;
    for (i = 0x20; i < 0x30; i++) { unsigned v = w[i]; if (v >= 100) s[n++] = '0' + v / 100; if (v >= 10) s[n++] = '0' + (v / 10) % 10; s[n++] = '0' + v % 10; s[n++] = i == 0x27 ? '|' : ' '; }
    s[n] = 0; gfx_rrect(0, 0, 160, 9, 0, (rgb_t){0, 0, 0}, 0.9f); gfx_text(80, 4.5f, s, &FONT7, (rgb_t){255, 255, 255}, "mm", 1);
}
/* Effect DB (in flash, found through RAM tables; same walk as the stock 0x18440): record of model <idx> in group <g> */
static const unsigned char *db_rec(int g, int idx)
{
    const unsigned char *hdr = *(const unsigned char *const volatile *)0x2000484Cu;                  /* gp-45556 */
    if (!hdr || g >= hdr[0x13]) return 0;
    const unsigned *list = *(const unsigned *const volatile *)(0x2000C3DCu + 4 * g);              /* gp-13924 */
    if (!list || idx >= (int)list[0]) idx = 0;
    unsigned base = *(const unsigned *)(hdr + 20 + 4 * g);
    return (const unsigned char *)(0x1A0000u + *(const unsigned *)(0x1A0004u + base + 4 * idx));
}
static unsigned rd32(const volatile unsigned char *p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((unsigned)p[3] << 24); }
static float f32(unsigned u) { union { unsigned u; float f; } x; x.u = u; return x.f; }
static void cpy(char *d, const unsigned char *s, int n) { int i; for (i = 0; i < n - 1 && s[i] >= 32 && s[i] < 127; i++) d[i] = s[i]; d[i] = 0; }
static void read_edit(model_t *m)
{
    int sel = *(volatile unsigned char *)0x2001BC31u, k;                                             /* CFW edit page: block */
    m->sel = sel < 9 ? sel : 0; { int b = *(volatile unsigned char *)0x2001BC32u; m->ksel = b - 1; }   /* CFW frame: 0 = block, 1.. = knob */ m->brand[0] = 0; m->nk = 0; m->mname[0] = 0;
    const unsigned char *r = db_rec(m->sel, M[0x244 + m->sel]);
    if (!r || r[8] == 0 || r[8] > 12) return;
    const unsigned char *sb = r + 16 + 24 * r[8];
    cpy(m->mname, sb, sizeof m->mname);
    for (k = 0; k < r[8] && k < 8; k++) {
        const unsigned char *kr = r + 16 + 24 * k; unsigned noff = kr[2] | (kr[3] << 8);
        float mn = f32(rd32(kr + 4)), mx = f32(rd32(kr + 8)), v = f32(rd32(M + 0x95 + 32 * m->sel + 4 * kr[20]));
        int pct = mx > mn ? (int)((v - mn) * 100.0f / (mx - mn) + 0.5f) : 0;
        cpy(m->kn[k], sb + noff, sizeof m->kn[k]); m->kv[k] = pct < 0 ? 0 : pct > 100 ? 100 : pct;
    }
    m->nk = k;
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
            if (ys > 0 && y1 <= 13) ys = 0;
            for (y = ys; y <= ye; y += SH) { int e = y + SH - 1 > ye ? ye : y + SH - 1;
                gfx_begin(0, 159, y, e, buf, &THEMES[0]); page_home(&m); FLUSH(0, 159, y, e, buf); }
            FREE(buf); gfx_bind(old); return;
        }
        gfx_begin(x1, x2, y1, y2, px, &THEMES[0]); page_home(&m);
    }
    gfx_bind(old);
    FLUSH(x1, x2, y1, y2, px);
}
