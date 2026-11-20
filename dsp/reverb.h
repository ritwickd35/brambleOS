#ifndef REVERB_H
#define REVERB_H
#include <stdint.h>
#include "pmfx.h"
#define RV_WORDS (1u << 19)              /* 2 MB of SDRAM */
#define RV_MAGIC 0x52565631u
#define RV_NER 6
#define RV_NAP 12
struct rv_voice {                        /* one per menu entry */
    float size, t60_min, t60_max, hf_ratio, diff, diff2, mod_ms, mod_rate, predelay_ms, width, wet_gain, spring, shimmer;
    float er_ms[RV_NER], er_g[RV_NER];
    int8_t k_mix, k_decay, k_damp, k_mod, k_hc, k_lc, pad0, pad1;
};
struct rv_state {
    uint32_t magic; const struct rv_voice *voice; uint32_t pos, words;
    uint32_t pre_base, pre_len, dif_base[4], dif_len[4], dif2_base[4], dif2_len[4], base[4], len[4], sh_base, sh_len, half;
    float d0[4], g[4], dmp[4], lp[4], ph[4], pair[2], outl[2], outr[2], ap[RV_NAP], sp_x, sp_y, sh_ph;
    float mod_d, wet, dry, pre, lpc, hpc, lpz, lpz2, hpx, hpx2, hpz_in, hpz_in2;
    hb_down dn; hb_up upl, upr;
};
void rv_set(const struct rv_voice *v, const float *p);
void rv_process(const struct rv_voice *v, float *buf, int n);
#endif
