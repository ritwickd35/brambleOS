/* in-place entry pairs for the 9 reverb voices (module image), state in RVB slot RAM, buffers in SDRAM */
#include "reverb.h"
/* timing probe: Mix knob at exactly 1 -> the right output channel carries the cycles spent in rv_process per
 * 64-frame block / 1e6 (smoothed); budget = 278,600 cycles per block at 192 MHz */
#define DEMCR (*(volatile uint32_t *)0xE000EDFCu)
#define DWTC (*(volatile uint32_t *)0xE0001000u)
#define CYC (*(volatile uint32_t *)0xE0001004u)
static float *const AVG = (float *)0x297EFF00u;
static void timed(const struct rv_voice *v, float *a, int k, const float *p)
{
    if (p && p[v->k_mix] == 2.f) { rv_process(v, a, k); for (int i = 0; i < k; i++) a[2 * i + 1] = 0.1f; return; }   /* calibration */
    if (p && p[v->k_mix] >= 3.f && p[v->k_mix] <= 6.f) {             /* memory micro-bench, 1024 reads */
        int t = (int)p[v->k_mix]; volatile float *b = t == 6 ? (volatile float *)0x10018400u : (volatile float *)0x29600000u;
        DEMCR |= 1u << 24; DWTC |= 1u; float acc = 0.f; uint32_t r = 12345u, t0 = CYC;
        if (t == 3 || t == 6) for (int i = 0; i < 1024; i++) { r = r * 1664525u + 1013904223u; acc += b[(r >> 12) & 0x3FFFu]; }
        else if (t == 4) for (int i = 0; i < 1024; i++) acc += b[i];
        else for (int i = 0; i < 1024; i++) { r = r * 1664525u + 1013904223u; b[(r >> 12) & 0x3FFFu] = acc; }
        float c = (float)(CYC - t0) + 0.f * acc;
        for (int i = 0; i < k; i++) a[2 * i + 1] = c * 1e-6f;
        return;
    }
    int dbg = p && p[v->k_mix] == 1.f;
    if (!dbg) { rv_process(v, a, k); return; }
    DEMCR |= 1u << 24; DWTC |= 1u; uint32_t t0 = CYC;
    rv_process(v, a, k);
    float c = (float)(CYC - t0) * (64.f / (float)k);
    float m = *AVG; if (!(m >= 0.f && m < 1e8f)) m = c; m += 0.02f * (c - m); *AVG = m;
    for (int i = 0; i < k; i++) a[2 * i + 1] = m * 1e-6f;
}
extern const struct rv_voice RV_VOICES[9];
#define PAIR(n) \
uint32_t rv##n##_e0(void *a, void *b) { (void)b; if (a) rv_set(&RV_VOICES[n], (const float *)a); return 0; } \
uint32_t rv##n##_e1(void *a, uint32_t k, void *c, void *d, void *e, void *f, void *g) \
{ (void)d; (void)f; (void)g; if (c) rv_set(&RV_VOICES[n], (const float *)c); \
  if (a && k && k <= 256) { timed(&RV_VOICES[n], (float *)a, (int)k, (const float *)c); } return 0; }
PAIR(0) PAIR(1) PAIR(2) PAIR(3) PAIR(4) PAIR(5) PAIR(6) PAIR(7) PAIR(8)
