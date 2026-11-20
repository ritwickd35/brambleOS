/* Smart noise gate: band-limited detector, hysteresis, hold, soft downward expansion with limited range,
 * gain computed every 8 samples and smoothed in the log domain (no chatter, no clicks). */
#ifndef GATE_H
#define GATE_H
#include "pmfx.h"
typedef struct {
    onepole det_hp, det_lp;
    float env, env_a, env_r;          /* detector envelope (linear) and coefficients */
    float thr_db, hyst_db, range_db, ratio;
    float g_db, att_c, rel_c;         /* smoothed gain (dB) */
    float g_lin, g_step;              /* per-sample linear gain ramp */
    int hold, hold_n, open, cnt;
} gate_t;
void gate_init(gate_t *s, float threshold, float decay, float range);   /* knobs 0..100 */
void gate_set(gate_t *s, float threshold, float decay, float range);   /* keeps envelope and gain */
void gate_process(gate_t *s, float *buf, int n, int stride);
#endif
