/* Multi Drv stub (the Grey Fuzz blob's own code, runs in the DRV slot RAM): copies the main part
 * (mod_drv2.c, linked right after this stub) from the module image into slot RAM when it is missing,
 * then calls it. tools/build_cut.py fills STAB. */
#include <stdint.h>
typedef uint32_t (*e0_t)(void *, void *);
typedef uint32_t (*e1_t)(void *, uint32_t, void *, void *, void *, void *, void *);
struct stab { uint32_t magic, src, dst, words, first, last, e0, e1; };
volatile const struct stab STAB __attribute__((section(".rodata.stab"))) = {0x42415453u};

static int ready(void)
{
    volatile const uint32_t *d = (volatile const uint32_t *)STAB.dst;
    if (d[0] == STAB.first && d[STAB.words - 1] == STAB.last) return 1;
    const uint32_t *s = (const uint32_t *)STAB.src;
    if (!s || !STAB.words || s[0] != STAB.first || s[STAB.words - 1] != STAB.last) return 0;
    for (uint32_t i = 0; i < STAB.words; i++) ((volatile uint32_t *)STAB.dst)[i] = s[i];
    return 1;
}

uint32_t lt_entry0(void *a, void *b) { return ready() ? ((e0_t)STAB.e0)(a, b) : 0; }

uint32_t lt_entry1(void *a, uint32_t n, void *c, void *d, void *e, void *f, void *g)
{
    if (!ready()) { *(volatile uint32_t *)(0x28000000u + 4u * 403u) = 0; return 0; }
    return ((e1_t)STAB.e1)(a, n, c, d, e, f, g);
}
