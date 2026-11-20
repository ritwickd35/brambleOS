/* Big Muff style: two cascaded soft-clipping gain stages, LP/HP blend tone (mid scoop), 4x + ADAA.
 * Knobs sustain, tone, volume (0..100). Formulas shared with drv_coefs.h. */
#ifndef MUFF_H
#define MUFF_H
#include "pmfx.h"
typedef struct { onepole in_hp, s1_hp, s1_lp, s2_hp, s2_lp, tone_lp, tone_hp; os4_up up; os4_down dn; adaa c1, c2; float g1, g2, tone, level; } muff_t;
void muff_init(muff_t *s, float sustain, float tone, float level);
void muff_process(muff_t *s, float *buf, int n, int stride);
#endif
