/* One drive model per DRV slot (build with -DMODEL=0 DS-1, 1 TS808, 2 RAT, 3 Fuzz). The blob's own program
 * image (main + library, tools/drives2.py assemble_packed) is put at engine code 0 by the stock loader, so this
 * code only sets up the engine data and the coefficients. Knobs: 1 drive, 2 tone, 3 level. */
#include "drv_coefs.h"

#if MODEL == 0                       /* only this model's tables end up in the slot */
#define CHM ds1_chain_at
#define HIM DS1_HI
#elif MODEL == 1
#define CHM ts808_chain_at
#define HIM TS808_HI
#elif MODEL == 2
#define CHM rat_chain_at
#define HIM RAT_HI
#elif MODEL == 3
#define CHM fuzz_chain_at
#define HIM FUZZ_HI
#elif MODEL == 4
#define CHM klon_chain_at
#define HIM KLON_HI
#else
#define CHM muff_chain_at
#define HIM MUFF_HI
#endif

static uint32_t magic;
static float kl[3];

static void update(const float *p)
{
    if (magic != 0x44525631u) {
        magic = 0x44525631u; EW[FLAG_W] = 0;
        for (uint32_t a = CONST_LO + NCONST; a < HIM; a++) EW[a] = 0;
        for (uint32_t i = 0; i < NCONST; i++) ED[CONST_LO + i] = CONST_VAL[i];
        for (uint32_t i = 0; i < NCHAIN; i++) ED[CHM[i]] = CHAIN_C[i];
    } else if (p[0] == kl[0] && p[1] == kl[1] && p[2] == kl[2]) return;
    coefs(MODEL, p[0], p[1], p[2]);
    kl[0] = p[0]; kl[1] = p[1]; kl[2] = p[2];
}

uint32_t drv_entry0(void *a, void *b) { (void)b; if (a) update((const float *)a); return 0; }

uint32_t drv_entry1(void *a, uint32_t n, void *c, void *d, void *e, void *f, void *g)
{
    (void)a; (void)n; (void)d; (void)f; (void)g;
    if (c) update((const float *)c);
    EW[FLAG_W] = (magic == 0x44525631u && e && *(volatile uint8_t *)e) ? 1u : 0u;
    return 0;
}
