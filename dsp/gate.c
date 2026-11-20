#include "gate.h"
#define CTL 8
void gate_init(gate_t *s, float threshold, float decay, float range)
{
    op_highpass(&s->det_hp, 120.f, PM_FS);              /* ignore hum and low-frequency rumble */
    op_lowpass(&s->det_lp, 3500.f, PM_FS);              /* ignore hiss: it is what we want to remove */
    s->env = 0.f;
    s->env_a = 1.f - pm_exp(-1.f / (0.0005f * PM_FS));  /* 0.5 ms attack */
    s->env_r = 1.f - pm_exp(-1.f / (0.030f * PM_FS));   /* 30 ms detector release */
    s->thr_db = -84.f + 0.6f * threshold;               /* -84 .. -24 dBFS */
    s->hyst_db = 6.f;
    s->range_db = 10.f + 0.7f * range;                  /* 10 .. 80 dB of attenuation */
    s->ratio = 4.f;                                      /* below threshold: 1 dB down -> 4 dB down */
    float rel_ms = 15.f + 4.85f * decay;                 /* gate close time 15 .. 500 ms */
    float fc = PM_FS / CTL;
    s->att_c = 1.f - pm_exp(-1.f / (0.0008f * fc));
    s->rel_c = 1.f - pm_exp(-1.f / (rel_ms * 0.001f * fc));
    s->g_db = 0.f; s->g_lin = 1.f; s->g_step = 0.f;
    s->hold_n = (int)(0.06f * fc);                       /* 60 ms hold */
    s->hold = 0; s->open = 1; s->cnt = 0;
}
void gate_set(gate_t *s, float threshold, float decay, float range)
{
    gate_t t; gate_init(&t, threshold, decay, range);
    s->thr_db = t.thr_db; s->range_db = t.range_db; s->rel_c = t.rel_c;
}
void gate_process(gate_t *s, float *buf, int n, int stride)
{
    for (int i = 0; i < n; i++) {
        float x = buf[i * stride];
        float d = op_run(&s->det_lp, op_run(&s->det_hp, x));
        d = d < 0 ? -d : d;
        s->env += (d > s->env ? s->env_a : s->env_r) * (d - s->env);
        if (++s->cnt >= CTL) {
            s->cnt = 0;
            float e_db = 8.6858896f * pm_log(s->env + 1e-9f);
            float target;
            if (s->open) {
                if (e_db < s->thr_db - s->hyst_db) { if (s->hold > 0) s->hold--; else s->open = 0; }
                else s->hold = s->hold_n;
            } else if (e_db > s->thr_db) { s->open = 1; s->hold = s->hold_n; }
            /* open: unity. closed: full range. The soft knee only acts in the hysteresis zone, so a closed gate
               does not follow the noise envelope (that was audible as "breathing"). */
            if (s->open) target = 0.f;
            else if (e_db > s->thr_db - s->hyst_db) target = (e_db - s->thr_db) * (s->ratio - 1.f) * 0.5f - 3.f;
            else target = -s->range_db;
            if (target < -s->range_db) target = -s->range_db;
            if (target > 0.f) target = 0.f;
            s->g_db += (target > s->g_db ? s->att_c : s->rel_c) * (target - s->g_db);
            float g = pm_db2lin(s->g_db);
            s->g_step = (g - s->g_lin) * (1.f / CTL);
        }
        s->g_lin += s->g_step;
        buf[i * stride] = x * s->g_lin;
    }
}
