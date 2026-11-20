/* Two-voice pitch shifter (FX2 Octave / Pitch). Per voice: two read taps sweeping a delay line in opposite phase,
 * each weighted by a Hann window (the two windows sum to 1), read rate = exact pitch ratio, linear interpolation.
 * Octave (default): knobs Low, High, Dry (0..100); voices -12 / +12 semitones.
 * Pitch (-DPITCH): knobs High (0..24 st), Low (0..24 st, sign ignored: always down), Dry, H-VOL, L-VOL.
 * Mono chain in the left channel, written to both. Buffer outside the loaded image (FX2 slot RAM).
 * Also builds for the Mac (host: -DHOST, buffer static). */
#include <stdint.h>
#include "pmfx.h"
#include "hann_tab.h"
#define NB 2048u                                   /* power of two */
#ifdef HOST
static float bufmem[NB];
#define BUF bufmem
#else
#define BUF ((float *)0x10009600u)
#endif
#define GRAIN 1536.f                               /* window length in samples (~35 ms) */

/* SOLA-style voice: one read tap drifts at (1 - ratio) samples per sample; before it leaves [DMIN, DMAX] a new tap is
 * started at the delay (in the opposite half of the range) whose waveform best matches the current tap (normalised
 * correlation over W samples, lag step 2), and the two are crossfaded over XF samples. Exact pitch, no fixed comb. */
#define DMIN 64.f
#define DMAX 1400.f
#ifndef XF
#define XF 256
#endif
#ifndef W
#define W 48
#endif
#define SEARCH 640
typedef struct { float d, d2, step, gain, c0, bs; int xf, lag, lag_end, best; } voice;   /* lag >= 0: search running */
#ifndef LAGSTEP
#define LAGSTEP 2
#endif
#ifndef WSTEP
#define WSTEP 6
#endif
#ifndef LPS
#define LPS 2
#endif
#define LPS_UNUSED                                      /* lags tried per sample: spreads the search over ~80 samples */
static voice v[2];
static uint32_t wpos, magic;
static float dry;
static float kl[5];

static float semis_to_ratio(float st) { return pm_exp(st * 0.05776227f); }   /* 2^(st/12) */
static void set_voice(voice *x, float ratio, float g) { x->step = 1.f - ratio; x->gain = g; }

void ps_params(const float *p)
{
#ifdef PITCH
    float hi = p[0], lo = p[1] < 0.f ? -p[1] : p[1];
    if (!(hi >= 0.f && hi <= 24.f && lo <= 24.f)) return;
    set_voice(&v[0], semis_to_ratio(hi), 0.01f * p[3]); set_voice(&v[1], semis_to_ratio(-lo), 0.01f * p[4]); dry = 0.01f * p[2];
    kl[0] = hi;
#else
    if (!(p[0] >= 0.f && p[0] <= 100.f && p[1] >= 0.f && p[1] <= 100.f && p[2] >= 0.f && p[2] <= 100.f)) return;
    set_voice(&v[0], 0.5f, 0.01f * p[0]); set_voice(&v[1], 2.f, 0.01f * p[1]); dry = 0.01f * p[2];
#endif
    if (magic != 0x50534833u) {
        for (uint32_t i = 0; i < NB; i++) BUF[i] = 0.f;
        wpos = 0; for (int k = 0; k < 2; k++) { v[k].d = 0.5f * (DMIN + DMAX); v[k].xf = 0; v[k].lag = -1; }
        magic = 0x50534833u;
    }
}

static inline float tap(float d)                   /* read d samples behind the write position */
{
    float r = (float)wpos - d; if (r < 0.f) r += (float)NB;
    uint32_t i = (uint32_t)r; float fr = r - (float)i;
    float a = BUF[i & (NB - 1)], b = BUF[(i + 1) & (NB - 1)];
    return a + fr * (b - a);
}
static inline float at(int32_t d) { return BUF[(wpos - (uint32_t)d) & (NB - 1)]; }

static void search_step(voice *q)
{
    int32_t c = (int32_t)q->c0 + (int32_t)((q->d - q->c0));      /* current tap, integer part, now */
    for (int r = 0; r < LPS && q->lag <= q->lag_end; r++, q->lag += LAGSTEP) {
        int32_t d = q->lag + (c - (int32_t)q->c0);              /* candidate keeps its offset to the drifting tap */
        float xy = 0.f, yy = 1e-9f;
        for (int32_t k = 0; k < W; k += WSTEP) { float a = at(c + k), bb = at(d + k); xy += a * bb; yy += bb * bb; }
        float sc = xy * xy / yy; if (xy < 0.f) sc = -sc;
        if (sc > q->bs) { q->bs = sc; q->best = q->lag; }
    }
}

void ps_process(float *buf, int n, int stride)
{
    if (magic != 0x50534833u) return;
    for (int i = 0; i < n; i++) {
        float x = buf[i * stride], y = dry * x;
        BUF[wpos] = x;
        for (int k = 0; k < 2; k++) {
            voice *q = &v[k]; if (q->gain <= 0.f) continue;
            if (!q->xf) {
                float mid = 0.5f * (DMIN + DMAX), lead = (float)(XF + SEARCH / (LAGSTEP * LPS) + 8);
                float nxt = q->d + q->step * lead;
                if (q->lag < 0 && (nxt > DMAX || nxt < DMIN)) {        /* start the search well before the splice */
                    q->c0 = q->d; q->lag = q->step > 0.f ? (int)DMIN : (int)mid; q->lag_end = q->lag + SEARCH; q->bs = -1e30f; q->best = q->lag;
                }
                if (q->lag >= 0) {
                    search_step(q);
                    if (q->lag > q->lag_end) {
                        q->d2 = (float)q->best + (q->d - q->c0);
                        if (q->step < 0.f && q->d2 + q->step * XF < DMIN) q->d2 = mid + SEARCH;
                        q->xf = XF; q->lag = -1;
                    }
                }
            }
            float s = tap(q->d);
            if (q->xf) {
                float g = (float)q->xf * (1.f / XF);    /* old tap fades out, new tap fades in */
                s = g * s + (1.f - g) * tap(q->d2);
                q->d2 += q->step;
                if (--q->xf == 0) q->d = q->d2;
            }
            q->d += q->step;
            y += q->gain * s;
        }
        wpos = (wpos + 1u) & (NB - 1u);
        buf[i * stride] = y;
    }
}

#ifndef HOST
static float pk[5];
uint32_t lt_entry0(void *a, void *b) { (void)b; if (a) { for (int i = 0; i < 5; i++) pk[i] = ((const float *)a)[i]; ps_params(pk); } return 0; }
uint32_t lt_entry1(void *a, uint32_t n, void *c, void *d, void *e, void *f, void *g)
{
    (void)c; (void)d; (void)f; (void)g; float *buf = (float *)a;
    if (!buf || n == 0 || n > 256) return 0;
    (void)e;
    ps_process(buf, (int)n, 2);
    for (uint32_t i = 0; i < n; i++) buf[2 * i + 1] = buf[2 * i];
    return 0;
}
#endif
