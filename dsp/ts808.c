#include "ts808.h"
#define FS4 (4.f * PM_FS)
static void coefs(ts808_t *s, float drive, float tone, float level, int reset)
{
    float d = drive * 0.01f, t = tone * 0.01f, l = level * 0.01f;
    onepole lp, tl;
    float rf = 51000.f + 500000.f * d * d;              /* feedback: 51k + 500k Drive pot (audio taper) */
    s->gain = rf / 4700.f;                               /* clipping-branch gain above unity: 11 .. 117 */
    float fc = 1.f / (6.2831853f * rf * 51e-12f); if (fc > 20000.f) fc = 20000.f;
    op_lowpass(&lp, fc, FS4);                            /* 51 pF across the feedback */
    op_lowpass(&tl, 600.f * pm_exp(2.3f * t), PM_FS);   /* tone: ~600 Hz (dark) .. ~6 kHz (bright) */
    if (reset) { s->fb_lp = lp; s->tone_lp = tl; }
    else { s->fb_lp.b0 = lp.b0; s->fb_lp.b1 = lp.b1; s->fb_lp.a1 = lp.a1; s->tone_lp.b0 = tl.b0; s->tone_lp.b1 = tl.b1; s->tone_lp.a1 = tl.a1; }
    s->tone = t;
    s->level = 1.5f * pm_db2lin(-30.f + 30.f * l);
}
void ts808_init(ts808_t *s, float drive, float tone, float level)
{
    op_highpass(&s->in_hp, 20.f, PM_FS);
    op_highpass(&s->fb_hp, 720.f, FS4);                 /* 4.7k + 47 nF: the mid hump */
    op_lowpass(&s->post_lp, 723.f * 4.f, PM_FS);         /* fixed treble cut after the clipper (1k + 220 nF) */
    os4_up_init(&s->up); os4_down_init(&s->dn); s->clip.x1 = s->clip.F1 = 0.f;
    coefs(s, drive, tone, level, 1);
}
void ts808_set(ts808_t *s, float drive, float tone, float level) { coefs(s, drive, tone, level, 0); }
void ts808_process(ts808_t *s, float *buf, int n, int stride)
{
    for (int i = 0; i < n; i++) {
        float x = op_run(&s->in_hp, buf[i * stride]);
        float u[4], v[4];
        os4_up_run(&s->up, x, u);
        for (int k = 0; k < 4; k++) {
            float b = op_run(&s->fb_lp, op_run(&s->fb_hp, u[k]) * s->gain);
            v[k] = u[k] + 0.55f * adaa_cubic(&s->clip, b * 1.8f);   /* diodes in the feedback: output = in + clipped branch */
        }
        float y = os4_down_run(&s->dn, v);
        y = op_run(&s->post_lp, y);
        float tl = op_run(&s->tone_lp, y);
        y = tl + s->tone * 0.6f * (y - tl);                 /* tone blends the darker and the brighter path */
        buf[i * stride] = y * s->level;
    }
}
