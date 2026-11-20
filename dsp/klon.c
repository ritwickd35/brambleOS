#include "klon.h"
#define FS4 (4.f * PM_FS)
void klon_init(klon_t *s, float g, float t, float l)
{
    float d = g * 0.01f; t *= 0.01f; l *= 0.01f;
    op_highpass(&s->in_hp, 20.f, PM_FS); op_highpass(&s->drv_hp, 400.f, FS4); op_lowpass(&s->gain_lp, 6000.f - 3000.f * d, FS4);
    op_highpass(&s->tre_hp, 1200.f, PM_FS); op_lowpass(&s->post_lp, 7000.f, PM_FS);
    os4_up_init(&s->up); os4_down_init(&s->dn); s->clip.x1 = s->clip.F1 = 0.f;
    s->gd = 2.f + 60.f * d * d; s->wd = 0.4f + 0.6f * d; s->wc = 1.f - 0.85f * d;
    s->treb = pm_db2lin(-10.f + 20.f * t) - 1.f; s->level = 1.5f * pm_db2lin(-30.f + 30.f * l);
}
void klon_process(klon_t *s, float *buf, int n, int stride)
{
    for (int i = 0; i < n; i++) {
        float x = op_run(&s->in_hp, buf[i * stride]), u[4], v[4];
        os4_up_run(&s->up, x, u);
        for (int k = 0; k < 4; k++) {
            float a = op_run(&s->gain_lp, op_run(&s->drv_hp, u[k]) * s->gd);
            v[k] = adaa_cubic(&s->clip, a) * s->wd + u[k] * s->wc;
        }
        float y = os4_down_run(&s->dn, v);
        y = y + s->treb * op_run(&s->tre_hp, y);
        buf[i * stride] = op_run(&s->post_lp, y) * s->level;
    }
}
