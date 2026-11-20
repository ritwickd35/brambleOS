/* NR module (replaces the stock Gate, one knob THRE): smart noise gate; decay 40, range 80 fixed. entry0(params) = knob change, entry1(buf, n, params, ..., &enable) = audio block
 * (buf = n interleaved stereo float frames; the chain is mono in the left channel). */
#include "gate.h"
static gate_t st;
static float k0 = -1;
static uint32_t magic;
static void apply(const float *p)
{
    if (!p) return;
    if (p[0] != k0) {
        if (magic != 0x47415445u) { gate_init(&st, p[0], 40.f, 80.f); magic = 0x47415445u; }
        else gate_set(&st, p[0], 40.f, 80.f);
        k0 = p[0];
    }
}
/* entry0 = parameter update (also sent repeatedly by the firmware): never reset the audio state here */
uint32_t lt_entry0(void *a, void *b) { (void)b; apply((const float *)a); return 0; }
uint32_t lt_entry1(void *a, uint32_t n, void *c, void *d, void *e, void *f, void *g)
{
    (void)d; (void)f; (void)g;
    if (e && *(volatile uint8_t *)e == 0) return 0;
    apply((const float *)c);
    float *buf = (float *)a;
    if (!buf || n == 0 || n > 256) return 0;
    gate_process(&st, buf, (int)n, 2);
    for (uint32_t i = 0; i < n; i++) buf[2 * i + 1] = buf[2 * i];
    return 0;
}
