/* FX1 module: DS-1 model. entry0(params) = knob change (the firmware also calls it repeatedly), entry1(buf, n, c, ...)
 * = audio block (buf = n interleaved stereo float frames; the chain is mono in the left channel).
 * Knobs are taken from entry0 only: entry1's third argument is not trusted (cut5/cut6: DS-1+ was broken on the
 * pedal although the same binary is clean in the ARM emulator).
 * Debug mode (VOL knob = 0): processes the audio normally but reports how long ds1_process takes, as muted
 * 0.125 s slots after 2000 blocks: 0 A55A | 1 n | 2 max SysTick ticks per block | 3 average | 4 blocks timed */
#include "ds1.h"
static ds1_t st;
static float k[3];
static uint32_t magic, dbg, blocks, tmax, tsum, tn;
static uint32_t val[5];
#define SLOT 86u
#define SYST_CVR (*(volatile uint32_t *)0xE000E018u)
static void apply(const float *p)
{
    if (!p) return;
    float d = p[0], t = p[1], l = p[2];
    if (!(d >= 0.f && d <= 100.f) || !(t >= 0.f && t <= 100.f) || !(l >= 0.f && l <= 100.f)) return;  /* ignore junk */
    if (magic != 0x44533122u) { ds1_init(&st, d, t, l); magic = 0x44533122u; blocks = 0; tmax = tsum = tn = 0; }
    else if (d != k[0] || t != k[1] || l != k[2]) ds1_set(&st, d, t, l);
    k[0] = d; k[1] = t; k[2] = l;
    dbg = (l == 0.f);
}
/* entry0 = parameter update: never reset the audio state here */
uint32_t lt_entry0(void *a, void *b) { (void)b; apply((const float *)a); return 0; }
static int bit(uint32_t slot)
{
    uint32_t v = slot / 22u, s = slot % 22u;
    if (v >= 5u) return 0;
    if (s < 3u) return 1;
    if (s == 3u || s >= 20u) return 0;
    return (val[v] >> (15u - (s - 4u))) & 1u;
}
uint32_t lt_entry1(void *a, uint32_t n, void *c, void *d, void *e, void *f, void *g)
{
    (void)c; (void)d; (void)f; (void)g;
    float *buf = (float *)a;
    if (magic != 0x44533122u || !buf || n == 0 || n > 256) return 0;
    if (e && *(volatile uint8_t *)e == 0) return 0;
    blocks++;
    uint32_t t0 = SYST_CVR;
    ds1_process(&st, buf, (int)n, 2);
    uint32_t dt = (t0 - SYST_CVR) & 0x00FFFFFFu;
    for (uint32_t i = 0; i < n; i++) buf[2 * i + 1] = buf[2 * i];
    if (dbg) {
        if (blocks > 100u && blocks <= 2000u) { if (dt > tmax) tmax = dt; tsum += dt >> 4; tn++; }
        if (blocks == 2001u) { val[0] = 0xA55Au; val[1] = n; val[2] = tmax > 0xFFFFu ? 0xFFFFu : tmax;
                               val[3] = tn ? ((tsum / tn) << 4) & 0xFFFFu : 0; val[4] = tn; if ((tsum / (tn ? tn : 1)) << 4 > 0xFFFFu) val[3] = 0xFFFFu; }
        if (blocks > 2001u && bit((blocks - 2002u) / SLOT)) for (uint32_t i = 0; i < 2u * n; i++) buf[i] = 0.f;
    }
    return 0;
}
