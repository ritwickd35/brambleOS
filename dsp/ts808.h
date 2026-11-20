/* "Scream" replacement: Ibanez TS808 style circuit model (diode-feedback op-amp clipper), 4x oversampled + ADAA. */
#ifndef TS808_H
#define TS808_H
#include "pmfx.h"
typedef struct {
    onepole in_hp, fb_hp, fb_lp, post_lp, tone_lp;
    os4_up up; os4_down dn; adaa clip;
    float gain, tone, level;
} ts808_t;
void ts808_init(ts808_t *s, float drive, float tone, float level);
void ts808_set(ts808_t *s, float drive, float tone, float level);
void ts808_process(ts808_t *s, float *buf, int n, int stride);
#endif
