#ifndef AMPDESC_H
#define AMPDESC_H
#include <stdint.h>
#include "amp.h"
struct ampdesc { float par[AMP_NPAR]; int8_t knob[8]; };     /* knob: gain bass mid treble pres vol bright -> param index */
uint32_t core_e0(void *a, void *b, const struct ampdesc *d);
uint32_t core_e1(void *c, void *e, const struct ampdesc *d);
#endif
