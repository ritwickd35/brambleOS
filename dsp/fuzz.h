/* "Grey Fuzz" replacement: Fuzz Face style model (two transistor stages as biased soft clippers), 4x + ADAA.
 * A behavioural model, not a component-level one: stage 1 fixed gain, stage 2 gain set by the fuzz knob
 * (emitter bypass), a bias offset gives the asymmetric, slightly "sputtery" character. */
#ifndef FUZZ_H
#define FUZZ_H
#include "pmfx.h"
typedef struct {
    onepole in_hp, mid_hp, out_lp, out_hp;
    os4_up up; os4_down dn; adaa c1, c2;
    float g1, g2, b1, b2, o1, o2, level;
} fuzz_t;
void fuzz_init(fuzz_t *s, float fuzz, float tone, float level);
void fuzz_set(fuzz_t *s, float fuzz, float tone, float level);
void fuzz_process(fuzz_t *s, float *buf, int n, int stride);
#endif
