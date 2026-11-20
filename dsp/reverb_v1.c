/* Shared reverb engine (RVB slots): pre-delay + early reflections + input diffusion + 8-line modulated FDN
 * (Householder) with per-line damping, optional spring dispersion and shimmer (+12 st in the feedback).
 * One copy of the code; each slot passes a voice (struct rv_voice) and its knob layout. Stereo in/out.
 * Pedal: runs in place from the module image, buffers in SDRAM (RV_MEM), state in RVB slot RAM (RV_STATE).
 * Host (-DHOST): static buffers. */
#include <stdint.h>
#include "pmfx.h"
#include "reverb.h"
static float pm_sqrt_fast(float x) { float r = x > 1.f ? x : 1.f; for (int i = 0; i < 6; i++) r = 0.5f * (r + x / r); return r; }

#ifdef HOST
static float rv_mem[RV_WORDS];
static struct rv_state rv_st;
#define MEM rv_mem
#define ST (&rv_st)
#else
#define MEM ((float *)0x29400000u)
#define ST ((struct rv_state *)0x297F0000u)     /* SDRAM: the RVB slot RAM is used by the shared stock reverb code */
#endif

static const float FDN_MS[8] = {29.7f, 37.1f, 41.1f, 43.7f, 53.9f, 59.3f, 67.1f, 73.3f};
static const float DIF_MS[4] = {4.77f, 3.59f, 12.73f, 9.30f};
static const float DIF2_MS[4] = {6.21f, 2.83f, 8.45f, 5.11f};   /* extra diffusion (plate, ambient) */
static const float LFO_HZ[8] = {0.31f, 0.47f, 0.53f, 0.71f, 0.37f, 0.59f, 0.83f, 0.43f};

static inline float rd(uint32_t base, uint32_t len, uint32_t pos, float d)    /* fractional read d behind pos */
{
    float r = (float)pos - d; if (r < 0.f) r += (float)len;
    uint32_t i = (uint32_t)r; float f = r - (float)i; uint32_t j = i + 1u; if (j >= len) j = 0;
    return MEM[base + i] + f * (MEM[base + j] - MEM[base + i]);
}

static float tri(float *ph, float inc) { float p = *ph + inc; if (p >= 1.f) p -= 1.f; *ph = p; return p < 0.5f ? 4.f * p - 1.f : 3.f - 4.f * p; }

static void knobs(const struct rv_voice *v, const float *p, float *mix, float *dec, float *damp, float *mod, float *hc, float *lc)
{
    *mix = v->k_mix >= 0 ? p[v->k_mix] * 0.01f : 0.3f;
    *dec = v->k_decay >= 0 ? p[v->k_decay] * 0.01f : 0.5f;
    *damp = v->k_damp >= 0 ? p[v->k_damp] * 0.01f : 0.5f;
    *mod = v->k_mod >= 0 ? p[v->k_mod] * 0.01f : 0.5f;
    *hc = v->k_hc < 0 ? 0.f : v->k_hc >= 64 ? 1.f - p[v->k_hc - 64] * 0.01f : p[v->k_hc] * 0.01f;   /* +64 = Tone (inverted) */
    *lc = v->k_lc >= 0 ? p[v->k_lc] * 0.01f : 0.f;
}

void rv_set(const struct rv_voice *v, const float *p)
{
    struct rv_state *s = ST; float mix, dec, damp, mod, hc, lc;
    knobs(v, p, &mix, &dec, &damp, &mod, &hc, &lc);
    if (s->magic != RV_MAGIC || s->voice != v) {                    /* (re)layout the delay memory */
        uint32_t a = 0;
        s->pre_len = (uint32_t)(0.25f * PM_FS) + 2u; s->pre_base = a; a += s->pre_len;
        for (int i = 0; i < 4; i++) {
            s->dif_len[i] = (uint32_t)(DIF_MS[i] * 0.001f * PM_FS * v->size) + 2u; s->dif_base[i] = a; a += s->dif_len[i];
            s->dif2_len[i] = (uint32_t)(DIF2_MS[i] * 0.001f * PM_FS * v->size) + 2u; s->dif2_base[i] = a; a += s->dif2_len[i];
        }
        for (int i = 0; i < 8; i++) {
            s->d0[i] = FDN_MS[i] * 0.001f * PM_FS * v->size; s->len[i] = (uint32_t)(s->d0[i] + 64.f); s->base[i] = a; a += s->len[i];
            s->lp[i] = 0.f; s->ph[i] = 0.125f * (float)i;
        }
        s->sh_base = a; s->sh_len = 4096u; a += s->sh_len; s->sh_ph = 0.f;
        for (uint32_t i = 0; i < a && i < RV_WORDS; i++) MEM[i] = 0.f;
        for (int i = 0; i < RV_NAP; i++) s->ap[i] = 0.f;
        s->pos = 0; s->words = a; s->voice = v; s->lpz = s->lpz2 = s->hpx = s->hpx2 = s->hpz_in = s->hpz_in2 = 0.f; s->sp_x = s->sp_y = 0.f;
        s->magic = RV_MAGIC;
    }
    float t60 = v->t60_min + (v->t60_max - v->t60_min) * dec * dec;          /* seconds at mid frequencies */
    float hf = v->hf_ratio * (1.f - 0.8f * damp);                               /* HF decay relative to mid */
    for (int i = 0; i < 8; i++) {
        float L = s->d0[i];
        s->g[i] = pm_exp(-6.9077553f * L / (PM_FS * t60));                      /* -60 dB after t60 */
        float ghf = pm_exp(-6.9077553f * L / (PM_FS * t60 * hf));
        float r = ghf / s->g[i]; if (r > 0.999f) r = 0.999f;                     /* one-pole damping: gain at Nyquist */
        s->dmp[i] = (1.f - r) / (1.f + r);
    }
    s->mod_d = v->mod_ms * 0.001f * PM_FS * (0.25f + 1.5f * mod);
    float norm = 1.f / pm_sqrt_fast(t60);                                      /* energy of the tail grows with t60 */
    s->wet = (mix < 0.5f ? 2.f * mix : 1.f) * v->wet_gain * norm; s->dry = mix > 0.5f ? 2.f - 2.f * mix : 1.f;   /* crossfade mix */
    s->pre = v->predelay_ms * 0.001f * PM_FS;
    float fhc = 16000.f * pm_exp(-2.0794415f * hc), flc = 20.f * pm_exp(3.4011974f * lc);  /* 16k..2k, 20..600 Hz */
    float k = 6.2831853f / PM_FS; s->lpc = fhc * k / (1.f + fhc * k); s->hpc = 1.f / (1.f + flc * k);
}

static inline float ap_proc(uint32_t base, uint32_t len, uint32_t pos, float x, float g)   /* Schroeder allpass */
{
    uint32_t r = pos % len; float d = MEM[base + r];
    float y = d - g * x; MEM[base + r] = x + g * y; return y;
}

void rv_process(const struct rv_voice *v, float *buf, int n)
{
    struct rv_state *s = ST; if (s->magic != RV_MAGIC || s->voice != v) return;
    const float k1 = 0.25f;                                                     /* Householder 2/N */
    for (int i = 0; i < n; i++) {
        float xl = buf[2 * i], xr = buf[2 * i + 1], x = 0.5f * (xl + xr);
        uint32_t pos = s->pos;
        /* pre-delay + early reflections */
        MEM[s->pre_base + pos % s->pre_len] = x;
        float in = rd(s->pre_base, s->pre_len, pos % s->pre_len, s->pre);
        float el = 0.f, er = 0.f;
        for (int t = 0; t < RV_NER; t++) {
            if (v->er_g[t] == 0.f) continue;
            float e = rd(s->pre_base, s->pre_len, pos % s->pre_len, s->pre + v->er_ms[t] * 0.001f * PM_FS) * v->er_g[t];
            if (t & 1) er += e; else el += e;
        }
        /* spring dispersion: chirpy allpass cascade in a short loop */
        if (v->spring) {
            float y = in + v->spring * s->sp_y;
            for (int k = 0; k < RV_NAP; k++) { float a = -0.62f, z = s->ap[k]; float o = a * y + z; s->ap[k] = y - a * o; y = o; }
            s->sp_y = rd(s->sh_base, s->sh_len, pos % s->sh_len, 1200.f) * 0.98f;
            MEM[s->sh_base + pos % s->sh_len] = y; in = y;
        }
        /* input diffusion */
        for (int d = 0; d < 4; d++) in = ap_proc(s->dif_base[d], s->dif_len[d], pos, in, v->diff);
        if (v->diff2 > 0.f) for (int d = 0; d < 4; d++) in = ap_proc(s->dif2_base[d], s->dif2_len[d], pos, in, v->diff2);
        /* FDN */
        float o[8], sum = 0.f;
        for (int l = 0; l < 8; l++) {
            float m = s->mod_d * tri(&s->ph[l], LFO_HZ[l] * v->mod_rate / PM_FS);
            float y = rd(s->base[l], s->len[l], pos % s->len[l], s->d0[l] + m);
            s->lp[l] += (1.f - s->dmp[l]) * (y - s->lp[l]);                   /* one-pole damping low-pass */
            o[l] = s->lp[l] * s->g[l]; sum += o[l];
        }
        float fb = in;
        if (v->shimmer > 0.f) {                                                  /* +12 st of the tail back in */
            float t = 0.25f * (o[0] + o[3] + o[5] + o[6]);
            MEM[s->sh_base + pos % s->sh_len] = t;
            float ph = s->sh_ph, ph2 = ph + 0.5f; if (ph2 >= 1.f) ph2 -= 1.f;
            float w1 = ph < 0.5f ? 2.f * ph : 2.f - 2.f * ph, w2 = 1.f - w1;
            float p1 = rd(s->sh_base, s->sh_len, pos % s->sh_len, 64.f + 2000.f * (1.f - ph));
            float p2 = rd(s->sh_base, s->sh_len, pos % s->sh_len, 64.f + 2000.f * (1.f - ph2));
            ph += 1.f / 2000.f; if (ph >= 1.f) ph -= 1.f; s->sh_ph = ph;
            fb += v->shimmer * (w1 * p1 + w2 * p2);
        }
        for (int l = 0; l < 8; l++) MEM[s->base[l] + pos % s->len[l]] = o[l] - k1 * sum + ((l & 1) ? -fb : fb) * 0.35f;
        float wl = el + (o[0] - o[2] + o[4] - o[6]) * 0.5f;                       /* disjoint line sets: decorrelated */
        float wr = er + (o[1] - o[3] + o[5] - o[7]) * 0.5f;
        float mid = 0.5f * (wl + wr), side = 0.5f * (wl - wr) * v->width;
        wl = mid + side; wr = mid - side;
        /* tone: high cut (low-pass) and low cut (high-pass) on the wet signal */
        s->lpz += s->lpc * (wl - s->lpz); s->lpz2 += s->lpc * (wr - s->lpz2);
        float hl = s->hpc * (s->hpx + s->lpz - s->hpz_in), hr = s->hpc * (s->hpx2 + s->lpz2 - s->hpz_in2);
        s->hpz_in = s->lpz; s->hpz_in2 = s->lpz2; s->hpx = hl; s->hpx2 = hr;
        buf[2 * i] = s->dry * xl + s->wet * hl;
        buf[2 * i + 1] = s->dry * xr + s->wet * hr;
        s->pos = pos + 1u;
    }
}
