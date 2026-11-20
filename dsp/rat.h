/* "Dark Mouse" replacement: ProCo RAT style model, 4x oversampled.
 * Op-amp gain = 1 + Rd/Z(560R+4.7uF) + Rd/Z(47R+2.2uF), 100 pF across Rd, gain-bandwidth limit,
 * rail clip, 1N914 diodes to ground (ADAA), RAT filter (1.5k + 100k pot, 3.3 nF), volume. */
#ifndef RAT_H
#define RAT_H
#include "pmfx.h"
typedef struct {
    onepole in_hp, hp_a, hp_b, gain_lp, gbw_lp, tone_lp;
    os4_up up; os4_down dn; adaa clip, railc;
    float ga, gb, level;
} rat_t;
void rat_init(rat_t *s, float dist, float tone, float level);   /* knobs 0..100, tone: higher = brighter */
void rat_set(rat_t *s, float dist, float tone, float level);
void rat_process(rat_t *s, float *buf, int n, int stride);
#endif
