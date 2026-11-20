/* in-place entry pairs for the 9 reverb voices (module image), state in RVB slot RAM, buffers in SDRAM */
#include "delay.h"
/* timing probe: Mix knob at exactly 1 -> the right output channel carries the cycles spent in dl_process per
 * 64-frame block / 1e6 (smoothed); budget = 278,600 cycles per block at 192 MHz */
#define DEMCR (*(volatile uint32_t *)0xE000EDFCu)
#define DWTC (*(volatile uint32_t *)0xE0001000u)
#define CYC (*(volatile uint32_t *)0xE0001004u)
static float *const AVG = (float *)0x297DFF00u;
static float *const E0P = (float *)0x297DFE80u;   /* e0's Time, Mix, F.Back (debug) */
static void timed(const struct dl_voice *v, float *a, int k, const float *p)
{
    if (p && p[v->k_mix] == 2.f) { dl_process(v, a, k); for (int i = 0; i < k; i++) a[2 * i + 1] = 0.1f; return; }   /* calibration */
    int dbg = p && p[v->k_mix] == 1.f;
    if (!dbg) { dl_process(v, a, k); return; }
    DEMCR |= 1u << 24; DWTC |= 1u; uint32_t t0 = CYC;
    dl_process(v, a, k);
    float c = (float)(CYC - t0) * (64.f / (float)k);
    float m = *AVG; if (!(m >= 0.f && m < 1e8f)) m = c; m += 0.02f * (c - m); *AVG = m;
    struct dl_state *st = (struct dl_state *)0x10018200u; float q = (p[2] == 16.f) ? st->wet : (p[2] == 17.f) ? st->y1 * 10.f : (p[2] == 18.f) ? ((float *)0x29600000u)[(st->pos + 47999u) % 48000u] * 10.f : (p[2] == 19.f) ? (float)st->pos * 1e-5f : (p[2] == 11.f) ? st->t * 1e-5f : (p[2] == 12.f) ? st->fb * 0.1f : (p[2] == 13.f) ? E0P[0] * 1e-6f : (p[2] == 14.f) ? E0P[1] * 1e-3f : (p[2] == 15.f) ? E0P[2] * 1e-3f : m * 1e-6f;
    for (int i = 0; i < k; i++) a[2 * i + 1] = q;
}
extern const struct dl_voice DL_VOICES[5];
#define PAIR(n) \
uint32_t dl##n##_e0(void *a, void *b) { if (b) dl_tempo(*(const int32_t *)b); if (a) dl_set(&DL_VOICES[n], (const float *)a); return 0; } \
uint32_t dl##n##_e1(void *a, uint32_t k, void *c, void *d, void *e, void *f, void *g) \
{ (void)d; (void)f; (void)g; /* knobs from e0 only: e1 params have no Time */ \
  if (a && k && k <= 256) { dl_process(&DL_VOICES[n], (float *)a, (int)k); }   /* release: no timing probe */ return 0; }
PAIR(0) PAIR(1) PAIR(2) PAIR(3) PAIR(4)
