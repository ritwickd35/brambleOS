/* Own clone engine (CLONE slot, code RAM 0x10003800): plays our NAM conversions ("PMAM" clone files) with our
 * multi-stage amp model (amp_core, linked for 0x10003C00 and carried in this module's image), followed by the
 * pedal's own cab stage (cab code copied to 0x10006400, cab engine program to code word 2816 at run time).
 * Cab: clone param 6 picks it live (0 = the capture's own cab from the file, k = kernel cab index k-1: factory
 * cab or User IR). The IR block itself must stay OFF in NAM presets (the CFW's IR-after-clone conflicts). Stock clones / empty slots: clean pass-through. */
#include "ampdesc.h"
typedef uint32_t (*e0_t)(void *, void *, const struct ampdesc *);
typedef uint32_t (*e1_t)(void *, void *, const struct ampdesc *);
typedef uint32_t (*cab0_t)(void *, void *);
typedef uint32_t (*cab1_t)(void *, uint32_t, void *, void *, void *, void *, void *);
typedef const void *(*getir_t)(int);
struct stab { uint32_t magic, src, dst, words, first, last, e0, e1; };
volatile const struct stab STAB __attribute__((section(".rodata.stab"))) = {0x42415453u};   /* amp core (in image) */
volatile const struct stab CTAB __attribute__((section(".rodata.stab"))) = {0x42415443u};   /* cab ARM code */
volatile const struct stab PTAB __attribute__((section(".rodata.stab"))) = {0x42415450u};   /* cab engine program */
#define CAB_E0 ((cab0_t)0x100064B5u)
#define CAB_E1 ((cab1_t)0x100067F9u)
#define GETIR ((getir_t)0x00006F0Du)          /* kernel: IR data pointer for a cab index (factory < 15 <= user) */
#define G ((volatile uint8_t *)0x20002AF4u)   /* kernel state: +0x0A enable bits, +0x175 cab index, +0x1A0 params */
#define FLAG_WORD 920u
struct st { struct ampdesc d; const uint8_t *clo; float prm[8]; uint32_t valid, src, idx; };   /* src: 0 none 1 file 2 IR block */
#define S (*(volatile struct st *)0x10006000u)

static int copy(volatile const struct stab *t)
{
    volatile uint32_t *d = (volatile uint32_t *)t->dst;
    if (d[0] == t->first && d[t->words - 1] == t->last) return 1;
    const uint32_t *s = (const uint32_t *)t->src;
    if (!s || !t->words || s[0] != t->first || s[t->words - 1] != t->last) return 0;
    for (uint32_t i = 0; i < t->words; i++) d[i] = s[i];
    return d[0] == t->first && d[t->words - 1] == t->last;
}

static void cab(const float *p)          /* cab choice = clone param 6 (index 5): 0 = the capture's own cab
                                           (or none), k > 0 = kernel cab index k - 1 (factory cabs, User IRs) */
{
    uint32_t want = p ? (uint32_t)p[5] : 0u;
    if (want == 0 && !*(const uint32_t *)(S.clo + 0x28)) want = 0xFFFFu;          /* amp only, no cab chosen */
    if (want == S.src) return;
    S.src = want; S.prm[0] = 50.0f;
    if (want == 0xFFFFu) return;
    const void *tp = want ? GETIR((int)want - 1) : (const void *)(S.clo + 0x288);
    CAB_E0((void *)S.prm, (void *)&tp);
}

uint32_t st_entry0(void *a, void *b)
{
    const uint8_t *c = b ? *(const uint8_t *const *)b : 0;
    S.valid = c && *(const uint32_t *)(c + 0x18) == 0x4D414D50u && copy(&STAB) && copy(&CTAB) && copy(&PTAB);
    if (!S.valid) return 0;
    S.clo = c; S.src = 0xFFFFFFFFu;
    const float *p = (const float *)(c + 0x88);
    for (int i = 0; i < AMP_NPAR; i++) S.d.par[i] = p[i];
    *(volatile uint32_t *)&S.d.knob[0] = 0x04030200u; *(volatile uint32_t *)&S.d.knob[4] = 0xFFFF01FFu;  /* gain bass mid treble | - vol - - */
    uint32_t r = ((e0_t)STAB.e0)(a, b, (const struct ampdesc *)&S.d);
    cab((const float *)a); return r;
}

uint32_t st_entry1(void *a, uint32_t n, void *c, void *d, void *e, void *f, void *g)
{
    if (!S.valid) { *(volatile uint32_t *)(0x28000000u + 4u * FLAG_WORD) = 0; return 0; }
    uint32_t r = ((e1_t)STAB.e1)(c, e, (const struct ampdesc *)&S.d);
    cab((const float *)c);
    volatile uint8_t en = S.src != 0xFFFFu;
    CAB_E1(a, n, (void *)S.prm, d, (void *)&en, f, g);
    return r;
}
