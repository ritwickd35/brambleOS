/* Our amp model: one fixed structure for every amp in the lineup, different settings per amp (fitted to the
 * measured stock amp). Preamp: 1-3 tube-like stages at 4x with ADAA; Yeh tone stack at 1x; push-pull power
 * stage at 2x with ADAA; presence / resonance shelves; output level.
 * Settings are a flat float array (AMP_NPAR), so the host, the fitter and the pedal share one format. */
#ifndef AMP_H
#define AMP_H
#include "pmfx.h"

enum {                       /* settings, in order */
    AP_NST,                  /* active preamp stages 1..3 (unused stages pass through) */
    AP_GMIN, AP_GMAX,        /* input gain at Gain = 0 and 100 (exponential taper) */
    AP_BRT_HZ, AP_BRT_DB,    /* bright cap: high shelf on the input when Bright is on */
    AP_S1,                   /* stage k (k = 0..2) at AP_S1 + 5k: hp_hz, lp_hz, gain, bias, out */
    AP_TS = AP_S1 + 15,      /* tone stack R1 R2 R3 R4 (ohm) C1 C2 C3 (farad) */
    AP_PDRV = AP_TS + 7,     /* power stage drive */
    AP_POUT,                 /* power stage output scale */
    AP_PRES_HZ, AP_PRES_DB,  /* presence: high shelf, +AP_PRES_DB at PRES = 100, 0 dB at PRES = 0 */
    AP_RES_HZ, AP_RES_DB,    /* resonance: fixed low shelf */
    AP_OUT,                  /* output gain at VOL = 50 */
    AP_OS,                   /* preamp oversampling: 2 or 4 */
    AP_OLP,                  /* output low-pass (Hz), 0 or >= 19000 = off */
    AMP_NPAR
};

typedef struct { float b[4], a[4], z[3]; } tstack;          /* 3rd order, transposed direct form II */
typedef struct { onepole hp, lp; adaa c; float g, b, o, off; } amp_stage;
typedef struct {
    float p[AMP_NPAR];
    onepole in_hp, brt_hp, pres_hp, res_lp, out_lp;
    os4_up up; os4_down dn; hb_up up2; hb_down dn2, dn2b; hb_up pre2; adaa pw;
    amp_stage st[3]; tstack ts;
    float gin, brt_g, pres_g, res_g, level;
    int nst, bright, os;
} amp_t;

/* knobs 0..100: gain bass middle treble presence volume; bright 0/1 */
void amp_init(amp_t *s, const float *par, const float *knobs, int bright);
void amp_set(amp_t *s, const float *knobs, int bright);
void amp_process(amp_t *s, float *buf, int n, int stride);
void tstack_coefs(float out_b[4], float out_a[4], const float *rc, float t, float m, float l, float fs);
#endif
