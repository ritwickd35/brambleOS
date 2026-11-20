/* Multi Drv, main part (copied into the DRV slot RAM by drv_stub.c). Knobs: 1 drive, 2 model
 * (0-24 DS-1, 25-49 TS808, 50-74 RAT, 75-100 Fuzz), 3 level, 5 tone. Engine library + per-model main
 * programs are read from the module image; tools/build_cut.py fills PTAB. */
#include <stdint.h>
#include "ds1.h"
#include "ts808.h"
#include "rat.h"
#include "fuzz.h"
#include "eng2.h"

#define ED ((volatile float *)0x28000000u)
#define EW ((volatile uint32_t *)0x28000000u)
#define EC ((volatile uint32_t *)0x28004000u)

struct ptab { uint32_t magic, addr[5], words[5], first[5], last[5]; };   /* [0] library, [1..4] mains */
volatile const struct ptab PTAB __attribute__((section(".rodata.ptab"))) = {0x42415450u};

static union { ds1_t d; ts808_t t; rat_t r; fuzz_t f; } S;
static uint32_t magic, model, bad;
static float kl[3];

static int load(uint32_t i, uint32_t at)
{
    const uint32_t *p = (const uint32_t *)PTAB.addr[i]; uint32_t n = PTAB.words[i];
    if (!p || !n || p[0] != PTAB.first[i] || p[n - 1] != PTAB.last[i]) return 0;
    for (uint32_t k = 0; k < n; k++) EC[at + k] = p[k];
    return 1;
}

static void wop(uint32_t a, const onepole *o) { ED[a] = o->b0; ED[a + 1] = o->b1; ED[a + 2] = o->a1; }

static void coefs(uint32_t m)
{
    switch (m) {
    case 0: wop(DS1_IN_HP, &S.d.in_hp); wop(DS1_BOOST_HP, &S.d.boost_hp); wop(DS1_OP_HP, &S.d.op_hp);
            wop(DS1_OP_LP, &S.d.op_lp); wop(DS1_CLIP_LP, &S.d.clip_lp); wop(DS1_TONE_LP, &S.d.tone_lp);
            wop(DS1_TONE_HP, &S.d.tone_hp); ED[DS1_S_BOOST] = S.d.boost; ED[DS1_S_OPGAIN] = S.d.opgain;
            ED[DS1_S_TONE] = S.d.tone; ED[DS1_S_LEVEL] = S.d.level; break;
    case 1: wop(TS808_IN_HP, &S.t.in_hp); wop(TS808_FB_HP, &S.t.fb_hp); wop(TS808_FB_LP, &S.t.fb_lp);
            wop(TS808_POST_LP, &S.t.post_lp); wop(TS808_TONE_LP, &S.t.tone_lp);
            ED[TS808_S_GAIN] = S.t.gain; ED[TS808_S_TONE] = S.t.tone; ED[TS808_S_LEVEL] = S.t.level; break;
    case 2: wop(RAT_IN_HP, &S.r.in_hp); wop(RAT_HP_A, &S.r.hp_a); wop(RAT_HP_B, &S.r.hp_b);
            wop(RAT_GAIN_LP, &S.r.gain_lp); wop(RAT_GBW_LP, &S.r.gbw_lp); wop(RAT_TONE_LP, &S.r.tone_lp);
            ED[RAT_S_GA] = S.r.ga; ED[RAT_S_GB] = S.r.gb; ED[RAT_S_LEVEL] = S.r.level; break;
    default: wop(FUZZ_IN_HP, &S.f.in_hp); wop(FUZZ_MID_HP, &S.f.mid_hp); wop(FUZZ_OUT_LP, &S.f.out_lp);
            wop(FUZZ_OUT_HP, &S.f.out_hp); ED[FUZZ_S_G1] = S.f.g1; ED[FUZZ_S_G2] = S.f.g2; ED[FUZZ_S_B1] = S.f.b1;
            ED[FUZZ_S_B2] = S.f.b2; ED[FUZZ_S_O1] = S.f.o1; ED[FUZZ_S_O2] = S.f.o2; ED[FUZZ_S_LEVEL] = S.f.level; break;
    }
}

static void init(uint32_t m, const float *k)
{
    switch (m) {
    case 0: ds1_init(&S.d, k[0], k[2], k[1]); break;
    case 1: ts808_init(&S.t, k[0], k[2], k[1]); break;
    case 2: rat_init(&S.r, k[0], k[2], k[1]); break;
    default: fuzz_init(&S.f, k[0], k[2], k[1]); break;
    }
}

static void set(uint32_t m, const float *k)
{
    switch (m) {
    case 0: ds1_set(&S.d, k[0], k[2], k[1]); break;
    case 1: ts808_set(&S.t, k[0], k[2], k[1]); break;
    case 2: rat_set(&S.r, k[0], k[2], k[1]); break;
    default: fuzz_set(&S.f, k[0], k[2], k[1]); break;
    }
}

static const unsigned short *const CH[4] = {ds1_chain_at, ts808_chain_at, rat_chain_at, fuzz_chain_at};
static const uint16_t LO[4] = {DS1_LO, TS808_LO, RAT_LO, FUZZ_LO}, HI[4] = {DS1_HI, TS808_HI, RAT_HI, FUZZ_HI};

static void start(uint32_t m, const float *k)
{
    EW[FLAG_W] = 0; model = m;
    bad = !(load(0, LIB_AT) && load(1 + m, 0));
    if (bad) return;
    for (uint32_t a = CONST_LO + NCONST; a < HI[m]; a++) EW[a] = 0;          /* scratch + model block */
    (void)LO;
    for (uint32_t i = 0; i < NCONST; i++) ED[CONST_LO + i] = CONST_VAL[i];
    for (uint32_t i = 0; i < NCHAIN; i++) ED[CH[m][i]] = CHAIN_C[i];
    init(m, k); coefs(m);
}

static void update(const float *p)
{
    float k[3] = {p[0], p[2], p[4]};
    uint32_t m = p[1] < 25.f ? 0u : p[1] < 50.f ? 1u : p[1] < 75.f ? 2u : 3u;
    if (magic != 0x44525632u || m != model) { magic = 0x44525632u; start(m, k); }
    else if (k[0] != kl[0] || k[1] != kl[1] || k[2] != kl[2]) { if (!bad) { set(m, k); coefs(m); } }
    else return;
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
