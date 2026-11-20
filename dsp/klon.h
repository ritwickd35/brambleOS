/* Klon Centaur style: clean path blended with a soft-clipped drive path (clean share falls as gain rises),
 * active treble shelf, 4x + ADAA. Knobs gain, treble, output (0..100). Formulas shared with drv_coefs.h. */
#ifndef KLON_H
#define KLON_H
#include "pmfx.h"
typedef struct { onepole in_hp, drv_hp, gain_lp, tre_hp, post_lp; os4_up up; os4_down dn; adaa clip; float gd, wc, wd, treb, level; } klon_t;
void klon_init(klon_t *s, float gain, float treble, float level);
void klon_process(klon_t *s, float *buf, int n, int stride);
#endif
