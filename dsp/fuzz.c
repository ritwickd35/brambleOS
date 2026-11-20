#include "fuzz.h"
#define FS4 (4.f * PM_FS)
static float cub(float x) { if (x > 1.f) return 2.f / 3; if (x < -1.f) return -2.f / 3; return x - x * x * x / 3.f; }
static void coefs(fuzz_t *s, float fz, float tone, float level, int reset)
{
    float f = fz * 0.01f, t = tone * 0.01f, l = level * 0.01f;
    onepole lp;
    s->g1 = 12.f;                                          /* Q1 */
    s->g2 = 2.f + 60.f * f * f;                            /* Q2, fuzz pot bypasses the emitter resistor */
    s->b1 = 0.10f; s->b2 = 0.25f;                           /* bias offsets -> asymmetric clipping */
    s->o1 = cub(s->b1); s->o2 = cub(s->b2);
    op_lowpass(&lp, 2500.f * pm_exp(1.6f * t), PM_FS);     /* ~2.5 kHz (dark) .. ~12 kHz (bright) */
    if (reset) s->out_lp = lp; else { s->out_lp.b0 = lp.b0; s->out_lp.b1 = lp.b1; s->out_lp.a1 = lp.a1; }
    s->level = 1.0f * pm_db2lin(-30.f + 30.f * l);
}
void fuzz_init(fuzz_t *s, float fz, float tone, float level)
{
    op_highpass(&s->in_hp, 60.f, PM_FS);                   /* 2.2 uF into the low input impedance */
    op_highpass(&s->mid_hp, 30.f, FS4);
    op_highpass(&s->out_hp, 40.f, PM_FS);
    os4_up_init(&s->up); os4_down_init(&s->dn);
    s->c1.x1 = s->c1.F1 = s->c2.x1 = s->c2.F1 = 0.f;
    coefs(s, fz, tone, level, 1);
}
void fuzz_set(fuzz_t *s, float fz, float tone, float level) { coefs(s, fz, tone, level, 0); }
void fuzz_process(fuzz_t *s, float *buf, int n, int stride)
{
    for (int i = 0; i < n; i++) {
        float x = op_run(&s->in_hp, buf[i * stride]), u[4], v[4];
        os4_up_run(&s->up, x, u);
        for (int k = 0; k < 4; k++) {
            float y = adaa_cubic(&s->c1, s->g1 * u[k] + s->b1) - s->o1;
            y = op_run(&s->mid_hp, y);
            v[k] = adaa_cubic(&s->c2, s->g2 * y + s->b2) - s->o2;
        }
        float y = os4_down_run(&s->dn, v);
        y = op_run(&s->out_hp, op_run(&s->out_lp, y));
        buf[i * stride] = y * s->level;
    }
}
