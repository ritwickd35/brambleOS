#ifndef DELAY_H
#define DELAY_H
#include <stdint.h>
#define DL_WORDS 48000u                  /* >= 1 s at full rate */
#define DL_MAGIC 0x444C5631u
struct dl_voice {                        /* one per menu entry */
    float half, lp_lo, lp_hi, hp, sat, in_sat, wow_hz, wow_ms, flut_hz, flut_ms, haas_ms, wet_gain, fb_max;
    int8_t k_mix, k_time, k_fb, k_tone, pad[4];
};
struct dl_state {
    uint32_t magic; const struct dl_voice *voice; uint32_t pos; int ph;
    float t, fb, wet, lpc, hpc, lpz, hpx, hpy, x1, y0, y1, r0, r1, wph, fph, half_in, kl[4], tempo;
};
void dl_set(const struct dl_voice *v, const float *p);
void dl_tempo(int32_t ms);
void dl_process(const struct dl_voice *v, float *buf, int n);
#endif
