/* SDRAM probe in an FX2 slot (temporary). Knob 1 (0..100) selects the test address: 0x29000000 + knob * 0x14000
 * (0 .. ~8 MB). At the first call a 4 KB block there is filled with a pattern; every block 16 words are re-checked
 * (rolling). Output: audio passes when the memory holds, the left channel is muted after the first mismatch. */
#include <stdint.h>
static volatile uint32_t *base; static uint32_t magic, bad, pos; static float knob = -99.f;
#define NW 1024u
static uint32_t pat(uint32_t i) { return 0xA5000000u ^ (i * 2654435761u); }
uint32_t lt_entry0(void *a, void *b) { (void)b; if (a) knob = ((const float *)a)[0]; return 0; }
uint32_t lt_entry1(void *a, uint32_t n, void *c, void *d, void *e, void *f, void *g)
{
    (void)c; (void)d; (void)e; (void)f; (void)g; float *buf = (float *)a;
    if (!buf || n == 0 || n > 256 || knob < -60.f) return 0;
    uint32_t k = knob < 0.f ? 100u : (uint32_t)knob;      /* Detune's range is -50..50: negative = positive control */
    if (magic != 0x4D454D31u + k) {
        base = (volatile uint32_t *)(0x29000000u + (k == 100u ? 40u : k) * 0x28000u);
        for (uint32_t i = 0; i < NW; i++) base[i] = pat(i);
        magic = 0x4D454D31u + k; bad = 0; pos = 0;
        if (k == 100u) base[7] ^= 1u;          /* positive control: must mute */
    }
    for (uint32_t j = 0; j < 16; j++) { if (base[pos] != pat(pos)) bad = 1; pos = (pos + 1) & (NW - 1); }
    for (uint32_t i = 0; i < n; i++) { buf[2 * i] *= bad ? 0.f : 0.5f; buf[2 * i + 1] = buf[2 * i]; }   /* -6 dB = probe alive and OK */
    return 0;
}
