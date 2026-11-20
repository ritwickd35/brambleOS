/* Per-amp stub (AMP slot RAM 0x10003800): copies the shared amp code from the module image into slot RAM at
 * 0x10003A00 when it is not there yet, then calls it with this amp's settings. tools/build_amps2.py fills DESC/STAB. */
#include "ampdesc.h"
typedef uint32_t (*e0_t)(void *, void *, const struct ampdesc *);
typedef uint32_t (*e1_t)(void *, void *, const struct ampdesc *);
struct stab { uint32_t magic, src, dst, words, first, last, e0, e1; };
volatile const struct stab STAB __attribute__((section(".rodata.stab"))) = {0x42415453u};
const struct ampdesc DESC __attribute__((section(".rodata.desc"))) = {{0}, {-1, -1, -1, -1, -1, -1, -1, -1}};

static int ready(void)
{
    volatile uint32_t *d = (volatile uint32_t *)STAB.dst;
    if (d[0] == STAB.first && d[STAB.words - 1] == STAB.last) return 1;
    const uint32_t *s = (const uint32_t *)STAB.src;
    if (!s || !STAB.words || s[0] != STAB.first || s[STAB.words - 1] != STAB.last) return 0;
    for (uint32_t i = 0; i < STAB.words; i++) d[i] = s[i];
    return d[0] == STAB.first && d[STAB.words - 1] == STAB.last;
}

uint32_t st_entry0(void *a, void *b) { return ready() ? ((e0_t)STAB.e0)(a, b, &DESC) : 0; }

uint32_t st_entry1(void *a, uint32_t n, void *c, void *d, void *e, void *f, void *g)
{
    (void)a; (void)n; (void)d; (void)f; (void)g;
    if (!ready()) { *(volatile uint32_t *)(0x28000000u + 4u * 920u) = 0; return 0; }
    return ((e1_t)STAB.e1)(c, e, &DESC);
}
