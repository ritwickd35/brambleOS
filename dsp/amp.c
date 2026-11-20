#include "amp.h"
#define FS4 (4.f * PM_FS)
#define FS2 (2.f * PM_FS)

static float cub(float x) { if (x > 1.f) return 2.f / 3; if (x < -1.f) return -2.f / 3; return x - x * x * x / 3.f; }

/* D. T. Yeh's three-knob tone stack (FMV), bilinear transform. rc = R1 R2 R3 R4 C1 C2 C3; t, m, l in 0..1
 * (l already tapered). Double precision: single precision cancels badly in these sums. */
void tstack_coefs(float ob[4], float oa[4], const float *rc, float t, float m, float l, float fs)
{
    double R1 = rc[0], R2 = rc[1], R3 = rc[2], R4 = rc[3], C1 = rc[4], C2 = rc[5], C3 = rc[6];
    double b1 = t * C1 * R1 + m * C3 * R3 + l * (C1 * R2 + C2 * R2) + (C1 * R3 + C2 * R3);
    double b2 = t * (C1 * C2 * R1 * R4 + C1 * C3 * R1 * R4) - m * m * (C1 * C3 * R3 * R3 + C2 * C3 * R3 * R3)
              + m * (C1 * C3 * R1 * R3 + C1 * C3 * R3 * R3 + C2 * C3 * R3 * R3)
              + l * (C1 * C2 * R1 * R2 + C1 * C2 * R2 * R4 + C1 * C3 * R2 * R4)
              + l * m * (C1 * C3 * R2 * R3 + C2 * C3 * R2 * R3)
              + (C1 * C2 * R1 * R3 + C1 * C2 * R3 * R4 + C1 * C3 * R3 * R4);
    double b3 = l * m * (C1 * C2 * C3 * R1 * R2 * R3 + C1 * C2 * C3 * R2 * R3 * R4)
              - m * m * (C1 * C2 * C3 * R1 * R3 * R3 + C1 * C2 * C3 * R3 * R3 * R4)
              + m * (C1 * C2 * C3 * R1 * R3 * R3 + C1 * C2 * C3 * R3 * R3 * R4)
              + t * C1 * C2 * C3 * R1 * R3 * R4 - t * m * C1 * C2 * C3 * R1 * R3 * R4
              + t * l * C1 * C2 * C3 * R1 * R2 * R4;
    double a0 = 1;
    double a1 = (C1 * R1 + C1 * R3 + C2 * R3 + C2 * R4 + C3 * R4) + m * C3 * R3 + l * (C1 * R2 + C2 * R2);
    double a2 = m * (C1 * C3 * R1 * R3 - C2 * C3 * R3 * R4 + C1 * C3 * R3 * R3 + C2 * C3 * R3 * R3)
              + l * m * (C1 * C3 * R2 * R3 + C2 * C3 * R2 * R3)
              - m * m * (C1 * C3 * R3 * R3 + C2 * C3 * R3 * R3)
              + l * (C1 * C2 * R2 * R4 + C1 * C2 * R1 * R2 + C1 * C3 * R2 * R4 + C2 * C3 * R2 * R4)
              + (C1 * C2 * R1 * R4 + C1 * C3 * R1 * R4 + C1 * C2 * R3 * R4 + C1 * C2 * R1 * R3 + C1 * C3 * R3 * R4 + C2 * C3 * R3 * R4);
    double a3 = l * m * (C1 * C2 * C3 * R1 * R2 * R3 + C1 * C2 * C3 * R2 * R3 * R4)
              - m * m * (C1 * C2 * C3 * R1 * R3 * R3 + C1 * C2 * C3 * R3 * R3 * R4)
              + m * (C1 * C2 * C3 * R3 * R3 * R4 + C1 * C2 * C3 * R1 * R3 * R3 - C1 * C2 * C3 * R1 * R3 * R4)
              + l * C1 * C2 * C3 * R1 * R2 * R4 + C1 * C2 * C3 * R1 * R3 * R4;
    double c = 2.0 * fs, c2 = c * c, c3 = c2 * c;
    double B0 = -b1 * c - b2 * c2 - b3 * c3, B1 = -b1 * c + b2 * c2 + 3 * b3 * c3;
    double B2 = b1 * c + b2 * c2 - 3 * b3 * c3, B3 = b1 * c - b2 * c2 + b3 * c3;
    double A0 = -a0 - a1 * c - a2 * c2 - a3 * c3, A1 = -3 * a0 - a1 * c + a2 * c2 + 3 * a3 * c3;
    double A2 = -3 * a0 + a1 * c + a2 * c2 - 3 * a3 * c3, A3 = -a0 + a1 * c - a2 * c2 + a3 * c3;
    ob[0] = (float)(B0 / A0); ob[1] = (float)(B1 / A0); ob[2] = (float)(B2 / A0); ob[3] = (float)(B3 / A0);
    oa[0] = 1.f; oa[1] = (float)(A1 / A0); oa[2] = (float)(A2 / A0); oa[3] = (float)(A3 / A0);
}

static inline float ts_run(tstack *f, float x)
{
    float y = f->b[0] * x + f->z[0];
    f->z[0] = f->b[1] * x - f->a[1] * y + f->z[1];
    f->z[1] = f->b[2] * x - f->a[2] * y + f->z[2];
    f->z[2] = f->b[3] * x - f->a[3] * y;
    return y;
}

static float db2g(float db) { return pm_db2lin(db) - 1.f; }       /* shelf: y = x + g * filtered(x) */

void amp_set(amp_t *s, const float *k, int bright)
{
    const float *p = s->p;
    float g = k[0] * 0.01f, bass = k[1] * 0.01f, mid = k[2] * 0.01f, tre = k[3] * 0.01f, pres = k[4] * 0.01f, vol = k[5] * 0.01f;
    s->gin = p[AP_GMIN] * pm_exp(g * pm_log(p[AP_GMAX] / p[AP_GMIN]));
    s->bright = bright; s->brt_g = bright ? db2g(p[AP_BRT_DB]) : 0.f;
    tstack_coefs(s->ts.b, s->ts.a, &p[AP_TS], tre, mid, pm_exp((bass - 1.f) * 3.4f), PM_FS);
    s->pres_g = db2g(p[AP_PRES_DB] * pres);
    s->level = p[AP_OUT] * pm_db2lin(40.f * (vol - 0.5f));          /* VOL: -20 .. +20 dB around AP_OUT */
}

void amp_init(amp_t *s, const float *par, const float *knobs, int bright)
{
    for (int i = 0; i < AMP_NPAR; i++) s->p[i] = par[i];
    const float *p = s->p;
    s->nst = (int)p[AP_NST]; s->os = p[AP_OS] == 2.f ? 2 : 4;
    float fso = s->os * PM_FS;
    op_highpass(&s->in_hp, 20.f, PM_FS); op_highpass(&s->brt_hp, p[AP_BRT_HZ], PM_FS);
    op_highpass(&s->pres_hp, p[AP_PRES_HZ], PM_FS); op_lowpass(&s->res_lp, p[AP_RES_HZ], PM_FS);
    s->res_g = db2g(p[AP_RES_DB]);
    { float f = p[AP_OLP]; if (f <= 0.f || f > 19000.f) f = 19000.f; op_lowpass(&s->out_lp, f, PM_FS); }
    os4_up_init(&s->up); os4_down_init(&s->dn); hb_up_init(&s->up2); hb_down_init(&s->dn2); hb_up_init(&s->pre2); hb_down_init(&s->dn2b);
    s->pw.x1 = s->pw.F1 = 0.f;
    for (int i = 0; i < 3; i++) {
        amp_stage *t = &s->st[i]; const float *q = &p[AP_S1 + 5 * i];
        float lim = 0.45f * fso;                       /* fits are done at 4x: keep corners below Nyquist at 2x */
        op_highpass(&t->hp, q[0] < lim ? q[0] : lim, fso); op_lowpass(&t->lp, q[1] < lim ? q[1] : lim, fso);
        t->g = q[2]; t->b = q[3]; t->o = q[4]; t->off = cub(q[3]); t->c.x1 = t->c.F1 = 0.f;
    }
    for (int i = 0; i < 3; i++) s->ts.z[i] = 0.f;
    amp_set(s, knobs, bright);
}

void amp_process(amp_t *s, float *buf, int n, int stride)
{
    for (int i = 0; i < n; i++) {
        float x = op_run(&s->in_hp, buf[i * stride]), u[4], w[2];
        x = (x + s->brt_g * op_run(&s->brt_hp, x)) * s->gin;
        if (s->os == 2) hb_up_run(&s->pre2, x, u); else os4_up_run(&s->up, x, u);
        for (int k = 0; k < s->os; k++) {
            float y = u[k];
            for (int j = 0; j < s->nst; j++) {
                amp_stage *t = &s->st[j];
                y = op_run(&t->lp, op_run(&t->hp, y));
                y = (adaa_cubic(&t->c, t->g * y + t->b) - t->off) * t->o;
            }
            u[k] = y;
        }
        float y = ts_run(&s->ts, s->os == 2 ? hb_down_run(&s->dn2b, u) : os4_down_run(&s->dn, u));
        hb_up_run(&s->up2, y, w);
        for (int k = 0; k < 2; k++) w[k] = adaa_cubic(&s->pw, s->p[AP_PDRV] * w[k]) * s->p[AP_POUT];
        y = hb_down_run(&s->dn2, w);
        y = y + s->pres_g * op_run(&s->pres_hp, y);
        y = y + s->res_g * op_run(&s->res_lp, y);
        buf[i * stride] = op_run(&s->out_lp, y) * s->level;
    }
}
