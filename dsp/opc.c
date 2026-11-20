/* opc lp|hp <fc> <fs>: one-pole coefficients exactly as pmfx.c computes them (b0 b1 a1) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pmfx.h"
int main(int c, char **v) { onepole o; float fc = atof(v[2]), fs = atof(v[3]);
    if (!strcmp(v[1], "lp")) op_lowpass(&o, fc, fs); else op_highpass(&o, fc, fs);
    printf("%.9gf, %.9gf, %.9gf\n", o.b0, o.b1, o.a1); return 0; }
