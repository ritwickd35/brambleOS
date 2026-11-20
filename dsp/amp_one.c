/* Our amp in an AMP slot: the coefficient maths of dsp/amp.c (same code as the offline model), results written to
 * the engine data RAM; the audio runs on the engine (tools/amps2.py program at code 1280). */
#include <stdint.h>
#include "amp.h"
#include "amp_eng.h"
#define ED ((volatile float *)0x28000000u)
#define EW ((volatile uint32_t *)0x28000000u)

static amp_t s;
static uint32_t magic;
static float kl[7];

static void put(uint32_t a, const onepole *o) { ED[a] = o->b0; ED[a + 1] = o->b1; ED[a + 2] = o->a1; }
static void knobs(const float *p, float k[6], int *b)
{
    for (int i = 0; i < 6; i++) k[i] = A_KNOB[i] >= 0 ? p[A_KNOB[i]] : 50.f;
    *b = A_KNOB[6] >= 0 ? (p[A_KNOB[6]] > 0.5f) : 0;
}
static void live(void)                       /* knob-dependent values */
{
    for (int i = 0; i < 4; i++) ED[A_TB0 + i] = s.ts.b[i];
    ED[A_TA1] = s.ts.a[1]; ED[A_TA2] = s.ts.a[2]; ED[A_TA3] = s.ts.a[3];
    ED[A_S_GIN] = s.gin; ED[A_S_BRTG] = s.brt_g; ED[A_S_PRESG] = s.pres_g; ED[A_S_LEVEL] = s.level;
}

static void update(const float *p)
{
    float k[6]; int b; knobs(p, k, &b);
    if (magic != 0x414D5031u) {
        magic = 0x414D5031u; EW[AFLAG] = 0;
        for (uint32_t a = A_LO; a < A_HI; a++) EW[a] = 0;
        for (uint32_t i = 0; i < A_NCONST; i++) ED[A_CONST_AT[i]] = A_CONST_VAL[i];
        for (uint32_t i = 0; i < A_NCHAIN; i++) ED[A_CHAIN_AT[i]] = A_CHAIN_C[i];
        amp_init(&s, A_PAR, k, b);
        put(A_IN_HP, &s.in_hp); put(A_BRT_HP, &s.brt_hp); put(A_PRES_HP, &s.pres_hp); put(A_RES_LP, &s.res_lp);
        const uint16_t hp[3] = {A_S0_HP, A_S1_HP, A_S2_HP}, lp[3] = {A_S0_LP, A_S1_LP, A_S2_LP};
        const uint16_t sg[3] = {A_S_S0_G, A_S_S1_G, A_S_S2_G}, sb[3] = {A_S_S0_B, A_S_S1_B, A_S_S2_B};
        const uint16_t so[3] = {A_S_S0_OFF, A_S_S1_OFF, A_S_S2_OFF}, sc[3] = {A_S_S0_O, A_S_S1_O, A_S_S2_O};
        for (int i = 0; i < 3; i++) {
            put(hp[i], &s.st[i].hp); put(lp[i], &s.st[i].lp);
            ED[sg[i]] = s.st[i].g; ED[sb[i]] = s.st[i].b; ED[so[i]] = s.st[i].off; ED[sc[i]] = s.st[i].o;
        }
        ED[A_S_PDRV] = s.p[AP_PDRV]; ED[A_S_POUT] = s.p[AP_POUT]; ED[A_S_RESG] = s.res_g;
        live();
    } else {
        int same = b == (int)kl[6];
        for (int i = 0; i < 6; i++) same &= k[i] == kl[i];
        if (same) return;
        amp_set(&s, k, b); live();
    }
    for (int i = 0; i < 6; i++) kl[i] = k[i];
    kl[6] = (float)b;
}

uint32_t amp_entry0(void *a, void *b) { (void)b; if (a) update((const float *)a); return 0; }

uint32_t amp_entry1(void *a, uint32_t n, void *c, void *d, void *e, void *f, void *g)
{
    (void)a; (void)n; (void)d; (void)f; (void)g;
    if (c) update((const float *)c);
    EW[AFLAG] = (magic == 0x414D5031u && e && *(volatile uint8_t *)e) ? 1u : 0u;
    return 0;
}
