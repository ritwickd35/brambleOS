#include "muff.h"
#define FS4 (4.f * PM_FS)
void muff_init(muff_t *s, float su, float t, float l)
{
    float d = su * 0.01f; t *= 0.01f; l *= 0.01f;
    op_highpass(&s->in_hp, 20.f, PM_FS); op_highpass(&s->s1_hp, 100.f, FS4); op_lowpass(&s->s1_lp, 6000.f, FS4);
    op_highpass(&s->s2_hp, 100.f, FS4); op_lowpass(&s->s2_lp, 4000.f, FS4);
    op_lowpass(&s->tone_lp, 408.f, PM_FS); op_highpass(&s->tone_hp, 1800.f, PM_FS);
    os4_up_init(&s->up); os4_down_init(&s->dn); s->c1.x1 = s->c1.F1 = s->c2.x1 = s->c2.F1 = 0.f;
    s->g1 = 2.f + 80.f * d * d; s->g2 = 20.f; s->tone = t; s->level = 2.f * pm_db2lin(-30.f + 30.f * l);
}
void muff_process(muff_t *s, float *buf, int n, int stride)
{
    for (int i = 0; i < n; i++) {
        float x = op_run(&s->in_hp, buf[i * stride]), u[4], v[4];
        os4_up_run(&s->up, x, u);
        for (int k = 0; k < 4; k++) {
            float y = adaa_cubic(&s->c1, op_run(&s->s1_hp, u[k]) * s->g1);
            y = op_run(&s->s1_lp, y);
            y = adaa_cubic(&s->c2, op_run(&s->s2_hp, y) * s->g2);
            v[k] = op_run(&s->s2_lp, y);
        }
        float y = os4_down_run(&s->dn, v);
        float lo = op_run(&s->tone_lp, y) * 1.3f * (1.f - s->tone), hi = op_run(&s->tone_hp, y) * 1.8f * s->tone;
        buf[i * stride] = (lo + hi) * s->level;
    }
}
