#include "ds1.h"
#define FS2 ((float)DS1_OS * PM_FS)   /* oversampled rate */
void ds1_init(ds1_t *s, float dist, float tone, float level)
{
    float d = dist * 0.01f, t = tone * 0.01f, l = level * 0.01f;
    op_highpass(&s->in_hp, 20.f, PM_FS);
    op_highpass(&s->boost_hp, 120.f, PM_FS);            /* transistor booster: bass roll-off before clipping */
    s->boost = 8.f;
    op_highpass(&s->op_hp, 72.f, FS2);                  /* 4.7k + 0.47uF in the op-amp's ground leg */
    float rd = 1000.f + 99000.f * d * d;                /* distortion pot (audio taper), ohms */
    s->opgain = rd / 4700.f;                            /* extra gain above unity: 0.2 .. 21 */
    float fc = 1.f / (6.2831853f * rd * 100e-12f); if (fc > 20000.f) fc = 20000.f;
    op_lowpass(&s->op_lp, fc, FS2);                     /* 100 pF across the pot */
    op_lowpass(&s->clip_lp, 7200.f, FS2);               /* 2.2k + 10 nF ahead of the diodes */
    op_lowpass(&s->tone_lp, 234.f, PM_FS);
    op_highpass(&s->tone_hp, 1060.f, PM_FS);
    s->tone = t;
    s->level = 3.0f * pm_db2lin(-30.f + 30.f * l);     /* level 50 ~ -15 dB re full */
#if DS1_OS == 4
    os4_up_init(&s->up); os4_down_init(&s->dn);
#else
    hb_up_init(&s->up); hb_down_init(&s->dn);
#endif
    s->trans.x1 = s->trans.F1 = s->diode.x1 = s->diode.F1 = 0.f;
}
static void keep(onepole *dst, const onepole *src) { dst->b0 = src->b0; dst->b1 = src->b1; dst->a1 = src->a1; }
void ds1_set(ds1_t *s, float dist, float tone, float level)
{
    ds1_t t; ds1_init(&t, dist, tone, level);
    keep(&s->op_lp, &t.op_lp);
    s->opgain = t.opgain; s->tone = t.tone; s->level = t.level;
}
void ds1_process(ds1_t *s, float *buf, int n, int stride)
{
    for (int i = 0; i < n; i++) {
        float x = op_run(&s->in_hp, buf[i * stride]);
        x = op_run(&s->boost_hp, x) * s->boost;
        float u[DS1_OS], v[DS1_OS];
#if DS1_OS == 4
        os4_up_run(&s->up, x, u);
#else
        hb_up_run(&s->up, x, u);
#endif
        for (int k = 0; k < DS1_OS; k++) {
#if DS1_TRANS_ADAA == 2
            float y = adaa_cubic(&s->trans, u[k] + 0.15f) - 0.148875f;  /* booster: bias gives the asymmetry (cub(0.15)) */
#elif DS1_TRANS_ADAA
            float y = adaa_asym(&s->trans, u[k], 1.4f);                 /* booster transistor, soft + asymmetric */
#else
            float y = u[k];                                              /* booster: soft asymmetric clip, no ADAA */
            if (y >= 0.f) { if (y > 1.f) y = 2.f / 3; else y = y - y * y * y / 3.f; }
            else { float z = 1.4f * y; if (z < -1.f) z = -1.f; y = (z - z * z * z / 3.f) / 1.4f; }
#endif
            y = y + s->opgain * op_run(&s->op_hp, y);                  /* non-inverting op-amp stage */
            y = op_run(&s->op_lp, y);
            y = op_run(&s->clip_lp, y);
            v[k] = adaa_cubic(&s->diode, y * 1.6f);                   /* silicon diode pair to ground */
        }
#if DS1_OS == 4
        float y = os4_down_run(&s->dn, v);
#else
        float y = hb_down_run(&s->dn, v);
#endif
        float lo = op_run(&s->tone_lp, y), hi = op_run(&s->tone_hp, y);
        y = (1.f - s->tone) * lo * 1.3f + s->tone * hi * 1.8f;
        buf[i * stride] = y * s->level;
    }
}
