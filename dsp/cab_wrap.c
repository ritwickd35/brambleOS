/* Cab Low cut / High cut: runs in place from the module image (linked at its image address, variables in free CAB
 * slot RAM above the stock code, zero growth of the cab blob). The stock entries get the IR through a
 * pointer in their second argument (float[512]); when a cut is active, a filtered copy is passed instead and the
 * stock code builds its convolution data from it (it normalises the level itself). Knobs: p[1] low cut, p[2] high cut. */
#include <stdint.h>
#include "pmfx.h"
#define N 512
typedef uint32_t (*e0_t)(void *, void *);
typedef uint32_t (*e1_t)(void *, uint32_t, void *, void *, void *, void *, void *);
#define S0 ((e0_t)0x100064B5u)
#define S1 ((e1_t)0x100067F9u)
#define SCR ((float *)0x10006D40u)          /* 2 KB filtered copy (+64 B copied header in front), above the code */
#define PRE 16                             /* the stock code also reads words in front of the IR pointer */
struct st { uint32_t magic; const float *src; float kl[2]; uint32_t sum; };
#define V ((struct st *)0x10006C80u)

static uint32_t hash(const float *p) { uint32_t h = 0; for (int i = 0; i < N; i += 7) h = h * 33u + ((const uint32_t *)p)[i]; return h; }

static int prepare(const float *p, const float *k)
{
    float lc = k[1], hc = k[2];
    if (lc < 0.5f && hc < 0.5f) return 0;
    uint32_t h = hash(p);
    if (V->magic == 0x43575031u && p == V->src && h == V->sum && lc == V->kl[0] && hc == V->kl[1]) return 1;
    for (int i = 1; i <= PRE; i++) SCR[-i] = p[-i];
    biquad a, b; int ua = lc >= 0.5f, ub = hc >= 0.5f;
    if (ua) bq_highpass(&a, 20.f * pm_exp(0.0270805f * lc), 0.707f, PM_FS);   /* 20 .. 300 Hz */
    if (ub) bq_lowpass(&b, 20000.f * pm_exp(-0.0207944f * hc), 0.707f, PM_FS); /* 20 .. 2.5 kHz */
    for (int i = 0; i < N; i++) { float y = p[i]; if (ua) y = bq_run(&a, y); if (ub) y = bq_run(&b, y); SCR[i] = y; }
    V->magic = 0x43575031u; V->src = p; V->sum = h; V->kl[0] = lc; V->kl[1] = hc; return 1;
}

uint32_t cw_entry0(void *a, void *b)
{
    const float **pp = (const float **)b;
    if (!a || !pp || !*pp || !prepare(*pp, (const float *)a)) return S0(a, b);
    const float *keep = *pp; *pp = SCR; uint32_t r = S0(a, b); *pp = keep; return r;
}

uint32_t cw_entry1(void *a, uint32_t n, void *c, void *d, void *e, void *f, void *g)
{
    return S1(a, n, c, d, e, f, g);          /* audio path untouched: its extra arguments are not the IR pointer */
}
