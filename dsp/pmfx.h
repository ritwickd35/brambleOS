/* pmfx: shared DSP building blocks for Pocket Master effects (mono, float, 44.1 kHz host rate).
 * The same sources build for the Mac (offline tests) and for the pedal (arm-none-eabi-gcc, Cortex-M4F). */
#ifndef PMFX_H
#define PMFX_H
#include <stdint.h>

#define PM_FS 44100.0f

/* ---- 2x oversampling: polyphase IIR half-band (hb_coefs.h, 6 all-pass sections, ~85 dB) ---- */
typedef struct { float x[6], y[6]; } hb_chain;
typedef struct { hb_chain a, b; } hb_up;
typedef struct { hb_chain a, b; float hold; } hb_down;
void hb_up_init(hb_up *s);
void hb_up_run(hb_up *s, float in, float out[2]);
void hb_down_init(hb_down *s);
float hb_down_run(hb_down *s, const float in[2]);
/* 4x = 2x (6 sections) then 2x (3 sections) */
typedef struct { hb_up s1; hb_up s2[1]; hb_chain a2, b2; } os4_up;
typedef struct { hb_down s1; hb_chain a2[2], b2[2]; } os4_down;
void os4_up_init(os4_up *s);
void os4_up_run(os4_up *s, float in, float out[4]);
void os4_down_init(os4_down *s);
float os4_down_run(os4_down *s, const float in[4]);

/* ---- one-pole filters (bilinear) ---- */
typedef struct { float b0, b1, a1, x1, y1; } onepole;
void op_lowpass(onepole *f, float fc, float fs);
void op_highpass(onepole *f, float fc, float fs);
static inline float op_run(onepole *f, float x)
{
    float y = f->b0 * x + f->b1 * f->x1 - f->a1 * f->y1;
    f->x1 = x; f->y1 = y; return y;
}

/* ---- biquad (transposed direct form II) ---- */
typedef struct { float b0, b1, b2, a1, a2, z1, z2; } biquad;
void bq_peak(biquad *f, float fc, float q, float gain_db, float fs);
void bq_lowpass(biquad *f, float fc, float q, float fs);
void bq_highpass(biquad *f, float fc, float q, float fs);
void bq_lowshelf(biquad *f, float fc, float gain_db, float fs);
void bq_highshelf(biquad *f, float fc, float gain_db, float fs);
static inline float bq_run(biquad *f, float x)
{
    float y = f->b0 * x + f->z1;
    f->z1 = f->b1 * x - f->a1 * y + f->z2;
    f->z2 = f->b2 * x - f->a2 * y;
    return y;
}

/* ---- antiderivative anti-aliased (ADAA, first order) clippers ---- */
typedef struct { float x1, F1; } adaa;
float adaa_cubic(adaa *s, float x);          /* f(x) = x - x^3/3 on |x|<1, +-2/3 outside */
float adaa_asym(adaa *s, float x, float k);  /* asymmetric version: negative side scaled by k */

/* ---- misc ---- */
float pm_db2lin(float db);
float pm_exp(float x);   /* fast, |rel err| < 1e-4 on [-20, 20] */
float pm_log(float x);   /* fast natural log, x > 0 */
#endif
