/* "JP Dist" replacement: Boss DS-1 style circuit model, 4x oversampled with ADAA clippers. */
#ifndef DS1_H
#define DS1_H
#include "pmfx.h"
typedef struct {
    onepole in_hp, boost_hp, op_hp, op_lp, clip_lp, tone_lp, tone_hp;
#ifndef DS1_OS
#define DS1_OS 4            /* oversampling factor: 2 or 4 */
#endif
#ifndef DS1_TRANS_ADAA
#define DS1_TRANS_ADAA 2    /* 1: asymmetric ADAA, 2: biased symmetric ADAA (engine version), 0: plain */
#endif
#if DS1_OS == 4
    os4_up up; os4_down dn;
#else
    hb_up up; hb_down dn;
#endif
    adaa trans, diode;
    float boost, opgain, tone, level;
} ds1_t;
void ds1_init(ds1_t *s, float dist, float tone, float level);  /* knobs 0..100 */
void ds1_set(ds1_t *s, float dist, float tone, float level);   /* knob change, keeps filter state */
void ds1_process(ds1_t *s, float *buf, int n, int stride);
#endif
