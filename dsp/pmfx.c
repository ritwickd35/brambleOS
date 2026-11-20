#include "pmfx.h"
#include "hb_coefs.h"
#include "hb2_coefs.h"

/* The pedal build has no libm: every transcendental below is our own. */
#define PI 3.14159265358979f

static float pm_tan(float x)   /* x in [0, 1.5]: tan via sin/cos polynomials */
{
    float x2 = x * x;
    float s = x * (1.f - x2 * (1.f / 6 - x2 * (1.f / 120 - x2 * (1.f / 5040 - x2 / 362880.f))));
    float c = 1.f - x2 * (0.5f - x2 * (1.f / 24 - x2 * (1.f / 720 - x2 * (1.f / 40320 - x2 / 3628800.f))));
    return s / c;
}
static float pm_sin(float x) { float t = x - PI / 2; return 1.f - t * t * (0.5f - t * t * (1.f / 24 - t * t * (1.f / 720 - t * t / 40320.f))); } /* x in [0, pi] */

float pm_exp(float x)
{
    if (x < -80.f) return 0.f;
    if (x > 80.f) x = 80.f;
    float t = x * 1.44269504f;            /* 2^t */
    int i = (int)(t < 0 ? t - 1 : t);
    float f = t - (float)i;
    float p = 1.f + f * (0.6931472f + f * (0.2402265f + f * (0.0555041f + f * (0.0096181f + f * 0.0013334f))));
    union { float f; int32_t i; } u; u.i = (i + 127) << 23;
    return p * u.f;
}

float pm_log(float x)
{
    union { float f; int32_t i; } u; u.f = x;
    int e = ((u.i >> 23) & 0xFF) - 127;
    u.i = (u.i & 0x007FFFFF) | 0x3F800000;   /* mantissa in [1,2) */
    float m = u.f, t = (m - 1.f) / (m + 1.f), t2 = t * t;
    float ln = 2.f * t * (1.f + t2 * (1.f / 3 + t2 * (1.f / 5 + t2 * (1.f / 7 + t2 / 9.f))));
    return ln + 0.69314718f * (float)e;
}

float pm_db2lin(float db) { return pm_exp(db * 0.11512925f); }

/* ---------------- half-band 2x ---------------- */
static inline float ap_chain(hb_chain *c, float x, int first)
{
    for (int i = first, k = 0; i < HB_N; i += 2, k++) {
        float y = hb_c[i] * (x - c->y[k]) + c->x[k];
        c->x[k] = x; c->y[k] = y; x = y;
    }
    return x;
}
void hb_up_init(hb_up *s) { for (int k = 0; k < 6; k++) s->a.x[k] = s->a.y[k] = s->b.x[k] = s->b.y[k] = 0.f; }
void hb_up_run(hb_up *s, float in, float out[2]) { out[0] = ap_chain(&s->a, in, 0); out[1] = ap_chain(&s->b, in, 1); }
void hb_down_init(hb_down *s) { hb_up_init((hb_up *)s); s->hold = 0.f; }
float hb_down_run(hb_down *s, const float in[2])
{
    float p0 = ap_chain(&s->a, in[1], 0);
    float p1 = ap_chain(&s->b, in[0], 1);
    return 0.5f * (p0 + p1);
}

/* ---------------- filters ---------------- */
void op_lowpass(onepole *f, float fc, float fs)
{
    float k = pm_tan(PI * fc / fs), n = 1.f / (1.f + k);
    f->b0 = k * n; f->b1 = k * n; f->a1 = (k - 1.f) * n; f->x1 = f->y1 = 0.f;
}
void op_highpass(onepole *f, float fc, float fs)
{
    float k = pm_tan(PI * fc / fs), n = 1.f / (1.f + k);
    f->b0 = n; f->b1 = -n; f->a1 = (k - 1.f) * n; f->x1 = f->y1 = 0.f;
}

/* RBJ cookbook */
static void bq_set(biquad *f, float b0, float b1, float b2, float a0, float a1, float a2)
{
    float n = 1.f / a0;
    f->b0 = b0 * n; f->b1 = b1 * n; f->b2 = b2 * n; f->a1 = a1 * n; f->a2 = a2 * n; f->z1 = f->z2 = 0.f;
}
static void bq_wcs(float fc, float fs, float *cw, float *sw)
{
    float w = 2.f * PI * fc / fs;
    *sw = pm_sin(w); *cw = (w <= PI / 2) ? pm_sin(PI / 2 - w) : -pm_sin(w - PI / 2);
}
void bq_peak(biquad *f, float fc, float q, float g, float fs)
{
    float A = pm_db2lin(g * 0.5f), cw, sw; bq_wcs(fc, fs, &cw, &sw); float al = sw / (2.f * q);
    bq_set(f, 1 + al * A, -2 * cw, 1 - al * A, 1 + al / A, -2 * cw, 1 - al / A);
}
void bq_lowpass(biquad *f, float fc, float q, float fs)
{
    float cw, sw; bq_wcs(fc, fs, &cw, &sw); float al = sw / (2.f * q);
    bq_set(f, (1 - cw) * 0.5f, 1 - cw, (1 - cw) * 0.5f, 1 + al, -2 * cw, 1 - al);
}
void bq_highpass(biquad *f, float fc, float q, float fs)
{
    float cw, sw; bq_wcs(fc, fs, &cw, &sw); float al = sw / (2.f * q);
    bq_set(f, (1 + cw) * 0.5f, -(1 + cw), (1 + cw) * 0.5f, 1 + al, -2 * cw, 1 - al);
}
static float pm_sqrt(float x) { if (x <= 0) return 0; float r = x > 1 ? x : 1; for (int i = 0; i < 12; i++) r = 0.5f * (r + x / r); return r; }
void bq_lowshelf(biquad *f, float fc, float g, float fs)
{
    float A = pm_db2lin(g * 0.5f), cw, sw; bq_wcs(fc, fs, &cw, &sw); float al = sw * 0.70710678f, sa = 2 * pm_sqrt(A) * al;
    bq_set(f, A * ((A + 1) - (A - 1) * cw + sa), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - sa),
           (A + 1) + (A - 1) * cw + sa, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - sa);
}
void bq_highshelf(biquad *f, float fc, float g, float fs)
{
    float A = pm_db2lin(g * 0.5f), cw, sw; bq_wcs(fc, fs, &cw, &sw); float al = sw * 0.70710678f, sa = 2 * pm_sqrt(A) * al;
    bq_set(f, A * ((A + 1) + (A - 1) * cw + sa), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - sa),
           (A + 1) - (A - 1) * cw + sa, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - sa);
}

/* ---------------- ADAA clippers ---------------- */
static inline float cub_f(float x) { if (x > 1.f) return 2.f / 3; if (x < -1.f) return -2.f / 3; return x - x * x * x / 3.f; }
static inline float cub_F(float x)
{
    float a = x < 0 ? -x : x;
    if (a > 1.f) return 2.f / 3 * a - 0.25f;
    float x2 = x * x; return 0.5f * x2 - x2 * x2 / 12.f;
}
float adaa_cubic(adaa *s, float x)
{
    float F = cub_F(x), d = x - s->x1, y;
    if (d > 1e-4f || d < -1e-4f) y = (F - s->F1) / d; else y = cub_f(0.5f * (x + s->x1));
    s->x1 = x; s->F1 = F; return y;
}
/* asymmetric: positive half = cubic(x), negative half = cubic(k*x)/k (softer, earlier or later clip) */
static inline float asy_f(float x, float k) { return x >= 0 ? cub_f(x) : cub_f(k * x) / k; }
static inline float asy_F(float x, float k) { return x >= 0 ? cub_F(x) : cub_F(k * x) / (k * k); }
float adaa_asym(adaa *s, float x, float k)
{
    float F = asy_F(x, k), d = x - s->x1, y;
    if (d > 1e-4f || d < -1e-4f) y = (F - s->F1) / d; else y = asy_f(0.5f * (x + s->x1), k);
    s->x1 = x; s->F1 = F; return y;
}

/* ---------------- 4x: second half-band stage with 3 sections ---------------- */
static inline float ap_chain2(hb_chain *c, float x, int first)
{
    for (int i = first, k = 0; i < HB2_N; i += 2, k++) {
        float y = hb2_c[i] * (x - c->y[k]) + c->x[k];
        c->x[k] = x; c->y[k] = y; x = y;
    }
    return x;
}
static void chain_clear(hb_chain *c) { for (int k = 0; k < 6; k++) c->x[k] = c->y[k] = 0.f; }
void os4_up_init(os4_up *s) { hb_up_init(&s->s1); chain_clear(&s->a2); chain_clear(&s->b2); }
void os4_up_run(os4_up *s, float in, float out[4])
{
    float m[2]; hb_up_run(&s->s1, in, m);
    for (int j = 0; j < 2; j++) { out[2 * j] = ap_chain2(&s->a2, m[j], 0); out[2 * j + 1] = ap_chain2(&s->b2, m[j], 1); }
}
void os4_down_init(os4_down *s) { hb_down_init(&s->s1); for (int j = 0; j < 2; j++) { chain_clear(&s->a2[j]); chain_clear(&s->b2[j]); } }
float os4_down_run(os4_down *s, const float in[4])
{
    float m[2];
    for (int j = 0; j < 2; j++) {
        float p0 = ap_chain2(&s->a2[0], in[2 * j + 1], 0), p1 = ap_chain2(&s->b2[0], in[2 * j], 1);
        m[j] = 0.5f * (p0 + p1);
    }
    return hb_down_run(&s->s1, m);
}
