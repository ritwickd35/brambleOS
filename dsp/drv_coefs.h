/* Coefficient maths shared by mod_drv3.c (Multi Drv) and mod_one.c (one model per slot). Formulas mirror
 * dsp/ds1.c, ts808.c, rat.c, fuzz.c. Model m: 0 DS-1, 1 TS808, 2 RAT, 3 Fuzz; knobs d, t, l in 0..100. */
#include <stdint.h>
#include "pmfx.h"
#include "eng2.h"
#include "muff_fixed.h"

#define ED ((volatile float *)0x28000000u)
#define EW ((volatile uint32_t *)0x28000000u)
#define EC ((volatile uint32_t *)0x28004000u)
#define FS PM_FS
#define FS4 (4.f * PM_FS)
#define TWO_PI 6.2831853f


static void lp(uint32_t a, float fc, float fs) { onepole o; op_lowpass(&o, fc, fs); ED[a] = o.b0; ED[a + 1] = o.b1; ED[a + 2] = o.a1; }
static void hp(uint32_t a, float fc, float fs) { onepole o; op_highpass(&o, fc, fs); ED[a] = o.b0; ED[a + 1] = o.b1; ED[a + 2] = o.a1; }
static float rc(float r, float c, float lim) { float f = 1.f / (TWO_PI * r * c); return f > lim ? lim : f; }
static float vol(float l, float k) { return k * pm_db2lin(-30.f + 30.f * l); }
static float cub(float x) { if (x > 1.f) return 2.f / 3; if (x < -1.f) return -2.f / 3; return x - x * x * x / 3.f; }

static void coefs(uint32_t m, float d, float t, float l)
{
    d *= 0.01f; t *= 0.01f; l *= 0.01f;
    if (m == 0) {
        float rd = 1000.f + 99000.f * d * d;
        hp(DS1_IN_HP, 20.f, FS); hp(DS1_BOOST_HP, 120.f, FS); hp(DS1_OP_HP, 72.f, FS4);
        lp(DS1_OP_LP, rc(rd, 100e-12f, 20000.f), FS4); lp(DS1_CLIP_LP, 7200.f, FS4);
        lp(DS1_TONE_LP, 234.f, FS); hp(DS1_TONE_HP, 1060.f, FS);
        ED[DS1_S_BOOST] = 8.f; ED[DS1_S_TB] = 0.15f; ED[DS1_S_TOFF] = cub(0.15f); ED[DS1_S_OPGAIN] = rd / 4700.f; ED[DS1_S_TONE] = t; ED[DS1_S_LEVEL] = vol(l, 3.f);
    } else if (m == 1) {
        float rf = 51000.f + 500000.f * d * d;
        hp(TS808_IN_HP, 20.f, FS); hp(TS808_FB_HP, 720.f, FS4); lp(TS808_POST_LP, 723.f * 4.f, FS);
        lp(TS808_FB_LP, rc(rf, 51e-12f, 20000.f), FS4); lp(TS808_TONE_LP, 600.f * pm_exp(2.3f * t), FS);
        ED[TS808_S_GAIN] = rf / 4700.f; ED[TS808_S_TONE] = t; ED[TS808_S_LEVEL] = vol(l, 1.5f);
    } else if (m == 2) {
        float rd = 100.f + 99900.f * d * d, ga = rd / 560.f, gb = rd / 47.f, fg = 1.0e6f / (1.f + ga + gb);
        float r = 1500.f + 100000.f * (1.f - t) * (1.f - t);
        hp(RAT_IN_HP, 20.f, FS); hp(RAT_HP_A, 60.f, FS4); hp(RAT_HP_B, 1540.f, FS4);
        lp(RAT_GAIN_LP, rc(rd, 100e-12f, 20000.f), FS4); lp(RAT_GBW_LP, fg > 20000.f ? 20000.f : fg, FS4);
        lp(RAT_TONE_LP, rc(r, 3.3e-9f, 16000.f), FS);
        ED[RAT_S_GA] = ga; ED[RAT_S_GB] = gb; ED[RAT_S_LEVEL] = vol(l, 1.2f);
    } else if (m == 4) {
        hp(KLON_IN_HP, 20.f, FS); hp(KLON_DRV_HP, 400.f, FS4); lp(KLON_GAIN_LP, 6000.f - 3000.f * d, FS4);
        hp(KLON_TRE_HP, 1200.f, FS); lp(KLON_POST_LP, 7000.f, FS);
        ED[KLON_S_GD] = 2.f + 60.f * d * d; ED[KLON_S_WD] = 0.4f + 0.6f * d; ED[KLON_S_WC] = 1.f - 0.85f * d;
        ED[KLON_S_TREB] = pm_db2lin(-10.f + 20.f * t) - 1.f; ED[KLON_S_LEVEL] = vol(l, 1.5f);
    } else if (m == 5) {
        for (int i = 0; i < 7; i++) { ED[MUFF_FA[i]] = MUFF_FC[3 * i]; ED[MUFF_FA[i] + 1] = MUFF_FC[3 * i + 1]; ED[MUFF_FA[i] + 2] = MUFF_FC[3 * i + 2]; }
        ED[MUFF_S_G1] = 2.f + 80.f * d * d; ED[MUFF_S_G2] = 20.f; ED[MUFF_S_LO] = 1.3f * (1.f - t); ED[MUFF_S_HI] = 1.8f * t;
        ED[MUFF_S_LEVEL] = vol(l, 2.f);
    } else {
        hp(FUZZ_IN_HP, 60.f, FS); hp(FUZZ_MID_HP, 30.f, FS4); hp(FUZZ_OUT_HP, 40.f, FS);
        lp(FUZZ_OUT_LP, 2500.f * pm_exp(1.6f * t), FS);
        ED[FUZZ_S_G1] = 12.f; ED[FUZZ_S_G2] = 2.f + 60.f * d * d; ED[FUZZ_S_B1] = 0.10f; ED[FUZZ_S_B2] = 0.25f;
        ED[FUZZ_S_O1] = cub(0.10f); ED[FUZZ_S_O2] = cub(0.25f); ED[FUZZ_S_LEVEL] = vol(l, 1.0f);
    }
}
