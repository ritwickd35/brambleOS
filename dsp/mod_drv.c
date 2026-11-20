/* Multi drive (DRV slot): the ARM side computes coefficients, the co-processor runs the model.
 * Knob 1 = drive, knob 2 = model (below 50: DS-1, from 50: TS808), knob 3 = level, knob 5 = tone.
 * Engine programs live in the module image; build_cut.py fills PTAB with their addresses. */
#include <stdint.h>
#include "ds1.h"
#include "ts808.h"
#include "eng_drives.h"

#define ED ((volatile float *)0x28000000u)
#define EW ((volatile uint32_t *)0x28000000u)
#define EC ((volatile uint32_t *)0x28004000u)
#define FLAG 0x193u

struct ptab { uint32_t magic, addr[2], words[2], first[2], last[2]; };
volatile const struct ptab PTAB __attribute__((section(".rodata.ptab"))) = {0x42415450u, {0, 0}, {0, 0}, {0, 0}, {0, 0}};
static uint32_t bad;

static union { ds1_t d; ts808_t t; } S;
static uint32_t magic, model;
static float k_last[3];

static int put_program(uint32_t m)                 /* 0 if the image copy does not look right */
{
    const uint32_t *p = (const uint32_t *)PTAB.addr[m]; uint32_t n = PTAB.words[m];
    if (!p || n == 0 || n > 0x500u || p[0] != PTAB.first[m] || p[n - 1] != PTAB.last[m]) return 0;
    for (uint32_t i = 0; i < n; i++) EC[i] = p[i];
    return 1;
}

static void write_coefs(uint32_t m)
{
    const float *f = (const float *)&S;
    if (m == 0) for (int i = 0; i < DS1_NCOEF; i++) ED[ds1_coef_addr[i]] = f[ds1_coef_off[i]];
    else for (int i = 0; i < TS808_NCOEF; i++) ED[ts808_coef_addr[i]] = f[ts808_coef_off[i]];
}

static void start(uint32_t m, const float *k)
{
    EW[FLAG] = 0;
    bad = !put_program(m);
    model = m;
    if (bad) return;                                /* stays in bypass */
    if (m == 0) {
        ds1_init(&S.d, k[0], k[2], k[1]);
        for (int i = 0; i < DS1_NCONST; i++) ED[ds1_const_addr[i]] = ds1_const_val[i];
        for (int i = 0; i < DS1_NZERO; i++) EW[ds1_zero_addr[i]] = 0;
    } else {
        ts808_init(&S.t, k[0], k[2], k[1]);
        for (int i = 0; i < TS808_NCONST; i++) ED[ts808_const_addr[i]] = ts808_const_val[i];
        for (int i = 0; i < TS808_NZERO; i++) EW[ts808_zero_addr[i]] = 0;
    }
    write_coefs(m);
}

/* k[0] drive, k[1] level, k[2] tone (0..100) */
static void knobs(const float *p, float *k) { k[0] = p[0]; k[1] = p[2]; k[2] = p[4]; }

static void update(const float *p)
{
    float k[3]; knobs(p, k);
    uint32_t m = p[1] < 50.0f ? 0u : 1u;
    if (magic != 0x44525631u || m != model) { magic = 0x44525631u; start(m, k); }
    else if (k[0] != k_last[0] || k[1] != k_last[1] || k[2] != k_last[2]) {
        if (m == 0) ds1_set(&S.d, k[0], k[2], k[1]); else ts808_set(&S.t, k[0], k[2], k[1]);
        if (!bad) write_coefs(m);
    } else return;
    k_last[0] = k[0]; k_last[1] = k[1]; k_last[2] = k[2];
}

uint32_t lt_entry0(void *a, void *b) { (void)b; if (a) update((const float *)a); return 0; }

uint32_t lt_entry1(void *a, uint32_t n, void *c, void *d, void *e, void *f, void *g)
{
    (void)a; (void)n; (void)d; (void)f; (void)g;
    if (c) update((const float *)c);
    EW[FLAG] = (!bad && e && *(volatile uint8_t *)e) ? 1u : 0u;
    return 0;
}
