/* Multi Drv, main part (copied into DRV slot RAM by drv_stub.c). Only the coefficient maths lives here;
 * the audio runs on the co-processor (tools/drives2.py). Formulas mirror dsp/ds1.c, ts808.c, rat.c, fuzz.c.
 * Knobs: 1 drive, 2 model (0-24 DS-1, 25-49 TS808, 50-74 RAT, 75-100 Fuzz), 3 level, 5 tone. */
#include "drv_coefs.h"

struct ptab { uint32_t magic, addr[5], words[5], first[5], last[5]; };   /* [0] library, [1..4] mains */
volatile const struct ptab PTAB __attribute__((section(".rodata.ptab"))) = {0x42415450u};

static uint32_t magic, model, bad;
static float kl[3];

static int load(uint32_t i, uint32_t at)
{
    const uint32_t *p = (const uint32_t *)PTAB.addr[i]; uint32_t n = PTAB.words[i];
    if (!p || !n || p[0] != PTAB.first[i] || p[n - 1] != PTAB.last[i]) return 0;
    for (uint32_t k = 0; k < n; k++) EC[at + k] = p[k];
    return 1;
}

static const unsigned short *const CH[4] = {ds1_chain_at, ts808_chain_at, rat_chain_at, fuzz_chain_at};
static const uint16_t HI[4] = {DS1_HI, TS808_HI, RAT_HI, FUZZ_HI};

static void update(const float *p)
{
    float k[3] = {p[0], p[4], p[2]};                           /* drive, tone, level */
    uint32_t m = p[1] < 25.f ? 0u : p[1] < 50.f ? 1u : p[1] < 75.f ? 2u : 3u;
    if (magic != 0x44525633u || m != model) {
        magic = 0x44525633u; model = m; EW[FLAG_W] = 0;
        bad = !(load(0, LIB_AT) && load(1 + m, 0));
        if (bad) return;
        for (uint32_t a = CONST_LO + NCONST; a < HI[m]; a++) EW[a] = 0;
        for (uint32_t i = 0; i < NCONST; i++) ED[CONST_LO + i] = CONST_VAL[i];
        for (uint32_t i = 0; i < NCHAIN; i++) ED[CH[m][i]] = CHAIN_C[i];
    } else if (k[0] == kl[0] && k[1] == kl[1] && k[2] == kl[2]) return;
    if (!bad) coefs(m, k[0], k[1], k[2]);
    kl[0] = k[0]; kl[1] = k[1]; kl[2] = k[2];
}

uint32_t drv_entry0(void *a, void *b) { (void)b; if (a) update((const float *)a); return 0; }

uint32_t drv_entry1(void *a, uint32_t n, void *c, void *d, void *e, void *f, void *g)
{
    (void)a; (void)n; (void)d; (void)f; (void)g;
    if (c) update((const float *)c);
    EW[FLAG_W] = (!bad && e && *(volatile uint8_t *)e) ? 1u : 0u;
    return 0;
}
