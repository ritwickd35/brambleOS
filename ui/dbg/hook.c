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
#define EW ((volatile unsigned char *)0x2000AB48u)            /* edit page data block (gp-20216) */
#define BOXES ((int (*)(void *))0x337D8u)                      /* number of child widgets (the original page's boxes) */
static int nboxes(void) { void *p = (void *)rd32(EW + 0xc); return p ? BOXES(p) : 0; }
static int edit_base(int sel, int nk)                  /* boxes before the first knob. Measured on the pedal across all reports: DRV, IR, EQ have 2; */
{                                                      /* NR, FX1, AMP (mode box), FX2, DLY, RVB have a third box that is not a knob */
    (void)nk; return (sel == 2 || sel == 4 || sel == 5) ? 2 : 3;
}
typedef float (*pget_t)(int, int);
#define PGET ((pget_t)0x5031Cu)                               /* knob value getter (module, knob) */
static void read_edit(model_t *m)
{
    const volatile unsigned char *w = (const volatile unsigned char *)0x2000AB48u;                    /* edit page data block */
    int slot = w[0x25], sel = slot < 10 ? M[0x63 + slot] : 0, k, g, mod;                              /* chain slot (updated at once by ◁/▷) -> block */
    if (sel == 9) sel = 3;                                                                            /* clone sits in the AMP place */
    m->sel = sel < 9 ? sel : 0; m->erow = w[0x2b]; m->ecol = w[0x2c]; m->eopen = w[0x28] != 0; m->ksel = -1;
    m->brand[0] = 0; m->nk = 0; m->mname[0] = 0;
    mod = (m->sel == 3 && m->nam) ? 9 : m->sel; g = mod;                                              /* AMP in clone mode = clone knobs */
    const unsigned char *r = db_rec(g, M[0x244 + mod]);
    if (!r || r[8] == 0 || r[8] > 12) return;
    const unsigned char *sb = r + 16 + 24 * r[8];
    cpy(m->mname, sb, sizeof m->mname); if (mod == 9) { const char *t = "NAM capture"; for (k = 0; t[k]; k++) m->brand[k] = t[k]; m->brand[k] = 0; }
    for (k = 0; k < r[8] && k < 8; k++) {
        const unsigned char *kr = r + 16 + 24 * k; unsigned noff = kr[2] | (kr[3] << 8);
        float mn = f32(rd32(kr + 4)), mx = f32(rd32(kr + 8)), v = PGET(mod, k);                       /* the pedal's own knob -> value mapping */
        int pct = mx > mn ? (int)((v - mn) * 100.0f / (mx - mn) + 0.5f) : 0;
        cpy(m->kn[k], sb + noff, sizeof m->kn[k]); m->kv[k] = pct < 0 ? 0 : pct > 100 ? 100 : pct; m->kmx[k] = (int)(mx + 0.5f); m->kraw[k] = (int)(v + 0.5f);
    }
    m->nk = k;
    /* The original numbers its boxes in one run, 3 per row: on/off, model, [mode: AMP only], then the knobs. */
    { int cell = m->erow * 3 + m->ecol, base = edit_base(m->sel, m->nk);
      if (cell == 0) { if (m->nk) { m->ekind = 0; m->ksel = 0; } else { m->ekind = 2; m->ksel = -1; } }   /* on/off is never a stop */
      else if (cell == 1) { m->ekind = 2; m->ksel = -1; }
      else if (cell == 2 && base == 3) { m->ekind = 3; m->ksel = -1; }                            /* 3rd box: mode / extra */
      else { m->ekind = 0; m->ksel = cell - base; if (m->ksel >= m->nk) m->ksel = 0; } }
}
/* ---- Edit page controls (Berry design) ----
 * The edit page's key table (RAM, rebuilt by the original on window entry) gets our handlers. They drive the original page's
 * own cursor (row 0x2B, column 0x2C) and open flag (0x28) and pass the event to the original logic, so every custom-firmware
 * feature keeps working: turn = change the highlighted item, push = next item, on/off = turn right/left on the ON item. */
typedef int (*kh_t)(void *, unsigned *);
#define KT ((volatile unsigned *)0x2000B554u)                 /* key table {msg, handler} (gp-17644) */
#define KN (*(volatile unsigned char *)0x200045A2u)           /* entries (gp-46238) */
#define O_TURN ((kh_t)0x16E96Eu)                              /* original: encoder turn (custom firmware) */
#define O_PUSH ((kh_t)0x1D034u)
#define O_LEFT ((kh_t)0x1C3B0u)
#define O_RIGHT ((kh_t)0x1C210u)
#define O_LONG ((kh_t)0x1C0ECu)
static void edit_state(model_t *m) { read_model(m); read_edit(m); }
static void paint(void (*pg)(const model_t *), const model_t *m, int ya, int yb)
{
    long long cb[4]; void *old = gfx_bind(cb); u16 *buf = (u16 *)MALLOC(160 * 8 * 2); int y, ye;
    if (buf) { for (y = ya; y <= yb; y += 8) { ye = y + 7 > yb ? yb : y + 7; gfx_begin(0, 159, y, ye, buf, &THEMES[0]); pg(m); FLUSH(0, 159, y, ye, buf); } FREE(buf); }
    gfx_bind(old);
}
#define edit_paint(m, a, b) paint(page_edit, m, a, b)
static void edit_paint_r(const model_t *m, int xa, int xb, int ya, int yb)
{
    long long cb[4]; void *old = gfx_bind(cb); int w = xb - xa + 1, y, ye; u16 *buf = (u16 *)MALLOC(w * 8 * 2);
    if (buf) { for (y = ya; y <= yb; y += 8) { ye = y + 7 > yb ? yb : y + 7; gfx_begin(xa, xb, y, ye, buf, &THEMES[0]); page_edit(m); FLUSH(xa, xb, y, ye, buf); } FREE(buf); }
    gfx_bind(old);
}
static void goto_item(const model_t *m, int kind, int ks)    /* put the original's cursor on an item; open it unless on/off */
{
    int base = edit_base(m->sel, m->nk), cell = kind == 0 ? base + ks : kind == 1 ? 0 : kind == 2 ? 1 : 2, nb = nboxes();
    if (nb > 0 && cell >= nb) cell = nb - 1;                                                        /* never past the last box */
    EW[0x2b] = cell / 3; EW[0x2c] = cell % 3; EW[0x28] = kind != 1;
}
static int k_push(void *c, unsigned *msg)                    /* next item: knobs -> model -> mode (AMP) -> knobs */
{
    model_t m; int kind, ks = 0; edit_state(&m); (void)c; (void)msg;
    if (m.ekind == 0 && m.ksel + 1 < m.nk) { kind = 0; ks = m.ksel + 1; }
    else if (m.ekind == 0 || m.ekind == 1) kind = 2;
    else if (m.ekind == 2 && m.sel == 3) kind = 3;                                                  /* AMP mode; other 3rd boxes are skipped */
    else { kind = m.nk ? 0 : 2; }
    goto_item(&m, kind, ks); edit_state(&m); edit_paint(&m, 44, 127); return 0;
}
static int k_turn(void *c, unsigned *msg)
{
    model_t m; int i, ks, old = -1; edit_state(&m);
    if (m.ekind == 1) { goto_item(&m, m.nk ? 0 : 2, 0); edit_state(&m); }                           /* never edit on/off by turning */
    goto_item(&m, m.ekind, m.ksel < 0 ? 0 : m.ksel); ks = m.ksel; if (m.ekind == 0) old = m.kv[ks];
    O_TURN(c, msg); edit_state(&m);
    if (m.ekind == 0) {
        if (old >= 0 && old != m.kv[ks]) {                                                            /* sweep: 2 frames, knob column only */
            int nv = m.kv[ks], x0 = 22 + 39 * (ks % 4) - 19; for (i = 1; i <= 2; i++) { m.kv[ks] = old + (nv - old) * i / 3; edit_paint_r(&m, x0, x0 + 38, 86, 122); } m.kv[ks] = nv; }
        edit_paint(&m, 0, 11); edit_paint(&m, 84, 127); return 0;
    }
    edit_paint(&m, 0, 127); return 0;
}
static int k_hold(void *c, unsigned *msg)                    /* hold the knob = block on/off; the highlight stays */
{
    model_t m; int kind, ks; edit_state(&m); kind = m.ekind == 1 ? 0 : m.ekind; ks = m.ksel < 0 ? 0 : m.ksel;
    goto_item(&m, 1, 0); O_PUSH(c, msg); edit_state(&m);
    goto_item(&m, kind, ks); edit_state(&m); edit_paint(&m, 0, 127); return 0;
}
/* Block movement. The original stops at both ends and keeps a hidden clone slot after RVB; we skip that slot and wrap round. */
#define O_INC O_LEFT                                           /* key 0 handler: slot + 1 */
#define O_DEC O_RIGHT                                          /* key 1 handler: slot - 1 */
static int is_clone(int s) { return s >= 0 && s < 10 && M[0x63 + s] == 9; }
static int last_real(void) { int s = 9; while (s > 0 && M[0x63 + s] == 9) s--; return s; }
static int chain_move(void *c, unsigned *msg, int inc)
{
    int before = EW[0x25], n = 0, target, at_end = inc ? before >= last_real() : before == 0; kh_t h = inc ? O_INC : O_DEC; model_t m;
    h(c, msg); if (is_clone(EW[0x25]) && EW[0x25] != before) h(c, msg);                            /* step over the hidden slot */
    if (at_end && (EW[0x25] == before || is_clone(EW[0x25]))) {                                    /* hit the end: wrap round */
        target = inc ? 0 : last_real(); while (EW[0x25] != target && n++ < 12) (EW[0x25] > target ? O_DEC : O_INC)(c, msg); }
    edit_state(&m); edit_paint(&m, 0, 127); return 0;
}
static int k_left(void *c, unsigned *msg) { return chain_move(c, msg, 1); }
static int k_right(void *c, unsigned *msg) { return chain_move(c, msg, 0); }
static int k_long(void *c, unsigned *msg) { int r = O_LONG(c, msg); model_t m; edit_state(&m); edit_paint(&m, 0, 127); return r; }
static void edit_keys(void)
{
    int i, n = KN; for (i = 0; i < n && i < 128; i++) { unsigned msg = KT[2 * i], h;
        h = msg == 3 ? (unsigned)k_turn : msg == 0x30202 ? (unsigned)k_push : (msg == 0x30002 || msg == 0x50002) ? (unsigned)k_left :
            (msg == 0x30102 || msg == 0x50102) ? (unsigned)k_right : msg == 0x40202 ? (unsigned)k_hold : (msg == 0x40002 || msg == 0x40102 || msg == 0x48002) ? (unsigned)k_long : 0;
        if (h && KT[2 * i + 1] != h) KT[2 * i + 1] = h; }
}
/* ---- Tuner (window 3) ----
 * The original tuner update calls a draw function with the fresh result (note, octave, cents); build_ui.py points those
 * two calls (signal / no signal) here. w1 bytes: [1] note, [3] octave; w0 = frequency (float bits); cents = rounded. */
void tuner_sig(void *ctx, unsigned w0, unsigned w1, unsigned w2, unsigned w3, unsigned w4, int cents)
{
    model_t m; int note = (signed char)(w1 >> 8), oct = (signed char)(w1 >> 24); float hz = f32(w0); (void)ctx; (void)w2; (void)w3; (void)w4;
    if (note >= 12) { oct = note / 12 - 1; note %= 12; }
    m.note = note < 0 ? -1 : note; m.octave = oct; m.cents = (signed char)cents; m.hz10 = hz > 10 && hz < 5000 ? (int)(hz * 10 + 0.5f) : 0; m.a4 = 0; m.mute = 0;
    paint(page_tuner, &m, 14, 127);
}
void tuner_nosig(void *ctx) { model_t m; (void)ctx; m.note = -1; m.a4 = 0; m.mute = 0; m.cents = 0; m.hz10 = 0; m.octave = 0; paint(page_tuner, &m, 14, 127); }
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
    } else if (WIN == 3) {
        gfx_bind(old); if (y1 <= 13) tuner_nosig(0);                                                  /* page entry: header + empty gauge */
        return;
    } else if (WIN == 10) {
        /* Our handlers repaint after every action; the original's own later updates are dropped, except a top-of-screen update
         * (page entry, preset change), which repaints the whole page once. */
        model_t m; edit_keys(); gfx_bind(old);
        if (y1 <= 13) { edit_state(&m); edit_paint(&m, 0, 127); }
        return;
    }
    gfx_bind(old);
    FLUSH(x1, x2, y1, y2, px);
}
