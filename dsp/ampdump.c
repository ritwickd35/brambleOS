/* ampdump <settings file> gain bass middle treble presence volume bright: prints the coefficients amp_init computes
 * (JSON, one line), so the engine data image uses exactly the pedal-side numbers. */
#include <stdio.h>
#include <stdlib.h>
#include "amp.h"
int main(int argc, char **argv)
{
    static amp_t s; float par[AMP_NPAR], kn[6] = {50, 50, 50, 50, 50, 50}; int brt = 0;
    if (argc < 2) return 1;
    FILE *f = fopen(argv[1], "r"); if (!f) return 1;
    for (int i = 0; i < AMP_NPAR; i++) if (fscanf(f, "%f", &par[i]) != 1) return 1;
    fclose(f);
    for (int i = 2; i < argc && i < 8; i++) kn[i - 2] = (float)atof(argv[i]);
    if (argc > 8) brt = atoi(argv[8]);
    amp_init(&s, par, kn, brt);
#define OP(n, x) printf("\"%s\": [%.9g, %.9g, %.9g], ", n, (double)(x).b0, (double)(x).b1, (double)(x).a1)
    printf("{");
    OP("in_hp", s.in_hp); OP("brt_hp", s.brt_hp); OP("pres_hp", s.pres_hp); OP("res_lp", s.res_lp); OP("out_lp", s.out_lp);
    for (int k = 0; k < 3; k++) {
        char a[8], b[8]; sprintf(a, "s%d_hp", k); sprintf(b, "s%d_lp", k); OP(a, s.st[k].hp); OP(b, s.st[k].lp);
        printf("\"s%d\": [%.9g, %.9g, %.9g, %.9g], ", k, (double)s.st[k].g, (double)s.st[k].b, (double)s.st[k].off, (double)s.st[k].o);
    }
    printf("\"tb\": [%.9g, %.9g, %.9g, %.9g], \"ta\": [%.9g, %.9g, %.9g], ", (double)s.ts.b[0], (double)s.ts.b[1], (double)s.ts.b[2],
           (double)s.ts.b[3], (double)s.ts.a[1], (double)s.ts.a[2], (double)s.ts.a[3]);
    printf("\"gin\": %.9g, \"brtg\": %.9g, \"pdrv\": %.9g, \"pout\": %.9g, \"presg\": %.9g, \"resg\": %.9g, \"level\": %.9g, \"nst\": %d}\n",
           (double)s.gin, (double)s.brt_g, (double)s.p[AP_PDRV], (double)s.p[AP_POUT], (double)s.pres_g, (double)s.res_g,
           (double)s.level, s.nst);
    return 0;
}
