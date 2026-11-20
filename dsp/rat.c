#include "rat.h"
#define FS4 (4.f * PM_FS)
static void coefs(rat_t *s, float dist, float tone, float level, int reset)
{
    float d = dist * 0.01f, t = tone * 0.01f, l = level * 0.01f;
    float rd = 100.f + 99900.f * d * d;                    /* distortion pot, audio taper */
    s->ga = rd / 560.f; s->gb = rd / 47.f;
    onepole glp, gbw, tl;
    float fc = 1.f / (6.2831853f * rd * 100e-12f); if (fc > 20000.f) fc = 20000.f;
    op_lowpass(&glp, fc, FS4);
    float gmax = 1.f + s->ga + s->gb, fg = 1.0e6f / gmax; if (fg > 20000.f) fg = 20000.f;   /* LM308 ~1 MHz GBW */
    op_lowpass(&gbw, fg, FS4);
    float r = 1500.f + 100000.f * (1.f - t) * (1.f - t);
    float ft = 1.f / (6.2831853f * r * 3.3e-9f); if (ft > 16000.f) ft = 16000.f;
    op_lowpass(&tl, ft, PM_FS);
    if (reset) { s->gain_lp = glp; s->gbw_lp = gbw; s->tone_lp = tl; }
    else {
        s->gain_lp.b0 = glp.b0; s->gain_lp.b1 = glp.b1; s->gain_lp.a1 = glp.a1;
        s->gbw_lp.b0 = gbw.b0; s->gbw_lp.b1 = gbw.b1; s->gbw_lp.a1 = gbw.a1;
        s->tone_lp.b0 = tl.b0; s->tone_lp.b1 = tl.b1; s->tone_lp.a1 = tl.a1;
    }
    s->level = 1.2f * pm_db2lin(-30.f + 30.f * l);
}
void rat_init(rat_t *s, float dist, float tone, float level)
{
    op_highpass(&s->in_hp, 20.f, PM_FS);
    op_highpass(&s->hp_a, 60.f, FS4);                      /* 560R + 4.7 uF */
    op_highpass(&s->hp_b, 1540.f, FS4);                    /* 47R + 2.2 uF */
    os4_up_init(&s->up); os4_down_init(&s->dn); s->clip.x1 = s->clip.F1 = s->railc.x1 = s->railc.F1 = 0.f;
    coefs(s, dist, tone, level, 1);
}
void rat_set(rat_t *s, float dist, float tone, float level) { coefs(s, dist, tone, level, 0); }
void rat_process(rat_t *s, float *buf, int n, int stride)
{
    for (int i = 0; i < n; i++) {
        float x = op_run(&s->in_hp, buf[i * stride]), u[4], v[4];
        os4_up_run(&s->up, x, u);
        for (int k = 0; k < 4; k++) {
            float a = s->ga * op_run(&s->hp_a, u[k]) + s->gb * op_run(&s->hp_b, u[k]);
            float y = u[k] + op_run(&s->gain_lp, a);
            y = 4.f * adaa_cubic(&s->railc, op_run(&s->gbw_lp, y) * 0.25f);   /* op-amp rails */
            v[k] = 0.9f * adaa_cubic(&s->clip, y * 1.5f);   /* diodes: ~0.6 V knee */
        }
        float y = os4_down_run(&s->dn, v);
        buf[i * stride] = op_run(&s->tone_lp, y) * s->level;
    }
}
