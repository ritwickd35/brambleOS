/* Shared delay engine (DLY slots): one mono delay line in SDRAM, optional half rate (dark units), loop low/high-pass,
 * loop saturation, preamp saturation, wow + flutter, Haas-widened wet output. Few SDRAM accesses per sample. */
#include "pmfx.h"
#include "delay.h"
#ifdef HOST
static float dl_mem[DL_WORDS]; static struct dl_state dl_st;
#define MEM dl_mem
#define ST (&dl_st)
#else
#define MEM ((float *)0x29600000u)
#ifndef DL_STATE
#define DL_STATE 0x10018200u          /* top of the DLY slot RAM (internal, fast) */
#endif
#define ST ((struct dl_state *)DL_STATE)
#endif

static inline float sat(float x) { if (x > 1.5f) return 1.f; if (x < -1.5f) return -1.f; return x - 0.148148148f * x * x * x; }
static inline float tri(float *ph, float inc) { float p = *ph + inc; if (p >= 1.f) p -= 1.f; *ph = p; return p < 0.5f ? 4.f * p - 1.f : 3.f - 4.f * p; }

static const float DIV[11] = {4.f, 2.f, 3.f, 1.3333333f, 1.f, 1.5f, 0.6666667f, 0.5f, 0.75f, 0.3333333f, 0.25f};   /* CFW note table */
void dl_tempo(int32_t ms) { if (ms >= 100 && ms <= 3000) ST->tempo = (float)ms; }

void dl_set(const struct dl_voice *v, const float *p)
{
    struct dl_state *s = ST;
    float mix = v->k_mix >= 0 ? p[v->k_mix] : 30.f, tms = v->k_time >= 0 ? p[v->k_time] : 400.f;
    float fb = v->k_fb >= 0 ? p[v->k_fb] * 0.01f : 0.3f, tone = v->k_tone >= 0 ? p[v->k_tone] * 0.02f : 0.5f;  /* Tone knob is 0..50 */
    if (s->magic != DL_MAGIC || s->voice != v) {
        for (uint32_t i = 0; i < DL_WORDS; i++) MEM[i] = 0.f;
        s->pos = 0; s->ph = 0; s->lpz = s->hpx = s->hpy = s->x1 = s->y0 = s->y1 = s->r0 = s->r1 = s->half_in = 0.f; s->wph = s->fph = 0.f;
        s->voice = v; s->magic = DL_MAGIC;
    }
    float fsl = v->half > 0.f ? 0.5f * PM_FS : PM_FS;
    if (tms >= 0.f && tms < 11.f) {                                    /* Time stored as a note value: beats x tempo */
        float tp = (s->tempo >= 100.f && s->tempo <= 3000.f) ? s->tempo : 500.f; tms = tp * DIV[(int)tms];
    }
    mix = mix > 1.001f ? mix * 0.01f : mix;                            /* e0 gets Mix as a fraction, e1 in percent */
    if (tms < 20.f) tms = 20.f;
    float t = tms * 0.001f * fsl, lim = (float)(DL_WORDS / (v->half > 0.f ? 1u : 1u)) - 64.f; if (t > lim) t = lim;
    s->t = t; s->fb = fb * v->fb_max; s->wet = mix * v->wet_gain;
    float flp = v->lp_lo * pm_exp(tone * pm_log(v->lp_hi / v->lp_lo)), k = 6.2831853f / fsl;
    s->lpc = flp * k / (1.f + flp * k); s->hpc = 1.f / (1.f + v->hp * k);
}

static inline uint32_t back(uint32_t pos, uint32_t d) { return pos >= d ? pos - d : pos + DL_WORDS - d; }

void dl_process(const struct dl_voice *v, float *buf, int n)
{
    struct dl_state *s = ST; if (s->magic != DL_MAGIC || s->voice != v) return;
    const int half = v->half > 0.f, haas = v->haas_ms > 0.f, mod = v->wow_ms > 0.f || v->flut_ms > 0.f, sv = v->sat > 0.f;
    const float fsl = half ? 0.5f * PM_FS : PM_FS, wa = v->wow_ms * 0.001f * fsl, wi = v->wow_hz / fsl;
    const float fa = v->flut_ms * 0.001f * fsl, fi = v->flut_hz / fsl, hd = v->haas_ms * 0.001f * fsl, insat = v->in_sat;
    const float satk = v->sat, isat = sv ? 1.f / v->sat : 0.f, iins = insat > 0.f ? 1.f / insat : 0.f;
    /* state in registers for the block */
    uint32_t pos = s->pos; int ph = s->ph;
    float t = s->t, fb = s->fb, wet = s->wet, lpc = s->lpc, hpc = s->hpc, lpz = s->lpz, hpx = s->hpx, hpy = s->hpy;
    float y0 = s->y0, y1 = s->y1, r0 = s->r0, r1 = s->r1, wph = s->wph, fph = s->fph, hin = s->half_in;
    for (int i = 0; i < n; i++) {
        float xl = buf[2 * i], xr = buf[2 * i + 1], x = 0.5f * (xl + xr), yl, yr;
        if (insat > 0.f) x = sat(x * insat) * iins;
        int go = 1;
        if (half) { if (!ph) { hin = x; go = 0; } else x = 0.5f * (x + hin); ph ^= 1; }
        if (go) {
            float d = t, y;
            if (mod) { d += wa * tri(&wph, wi) + fa * tri(&fph, fi);
                float r = (float)pos - d; if (r < 0.f) r += (float)DL_WORDS; uint32_t k = (uint32_t)r; float f = r - (float)k;
                uint32_t j = k + 1u == DL_WORDS ? 0u : k + 1u; y = MEM[k] + f * (MEM[j] - MEM[k]); }
            else y = MEM[back(pos, (uint32_t)d)];
            lpz += lpc * (y - lpz); y = hpc * (hpy + lpz - hpx); hpx = lpz; hpy = y;
            float w = x + fb * y; if (sv) w = sat(w * satk) * isat;
            MEM[pos] = w; pos = pos + 1u == DL_WORDS ? 0u : pos + 1u;
            y0 = y1; y1 = y; r0 = r1; if (haas) r1 = MEM[back(pos, (uint32_t)(d + hd) + 1u)];
        }
        if (half) { yl = ph ? y1 : 0.5f * (y0 + y1); yr = ph ? r1 : 0.5f * (r0 + r1); } else { yl = y1; yr = r1; }
        if (!haas) yr = yl;
        buf[2 * i] = xl + wet * yl; buf[2 * i + 1] = xr + wet * yr;
    }
    s->pos = pos; s->ph = ph; s->lpz = lpz; s->hpx = hpx; s->hpy = hpy; s->y0 = y0; s->y1 = y1; s->r0 = r0; s->r1 = r1;
    s->wph = wph; s->fph = fph; s->half_in = hin;
}
