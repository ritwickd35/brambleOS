/* offline host: host <effect> [knobs...] < in.f32 > out.f32   (mono float32 at 44.1 kHz)
 *   host amp <settings file> gain bass middle treble presence volume bright */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ds1.h"
#include "gate.h"
#include "ts808.h"
#include "rat.h"
#include "fuzz.h"
#include "amp.h"
#include "klon.h"
#include "muff.h"
void ps_params(const float *p); void ps_process(float *buf, int n, int stride);
int main(int argc, char **argv)
{
    static float buf[64];
    if (argc < 2) return 1;
    ds1_t d; gate_t g; ts808_t ts; rat_t rt; fuzz_t fz; static amp_t am; klon_t kl; muff_t mf; int which = 0;
    float k[8] = {50, 50, 50, 50, 50, 50, 50, 50};
    for (int i = 2; i < argc && i < 10; i++) k[i - 2] = (float)atof(argv[i]);
    if (!strcmp(argv[1], "ds1")) { ds1_init(&d, k[0], k[1], k[2]); which = 1; }
    else if (!strcmp(argv[1], "gate")) { gate_init(&g, k[0], k[1], k[2]); which = 2; }
    else if (!strcmp(argv[1], "ts808")) { ts808_init(&ts, k[0], k[1], k[2]); which = 3; }
    else if (!strcmp(argv[1], "rat")) { rat_init(&rt, k[0], k[1], k[2]); which = 4; }
    else if (!strcmp(argv[1], "fuzz")) { fuzz_init(&fz, k[0], k[1], k[2]); which = 5; }
    else if (!strcmp(argv[1], "amp") && argc > 2) {
        float par[AMP_NPAR] = {0}, kn[6] = {50, 50, 50, 50, 50, 50}; int brt = 0;
        FILE *f = fopen(argv[2], "r"); if (!f) return 1;
        for (int i = 0; i < AMP_NPAR; i++) if (fscanf(f, "%f", &par[i]) != 1) return 1;
        fclose(f);
        for (int i = 3; i < argc && i < 9; i++) kn[i - 3] = (float)atof(argv[i]);
        if (argc > 9) brt = atoi(argv[9]);
        amp_init(&am, par, kn, brt); which = 6;
    }
    else if (!strcmp(argv[1], "klon")) { klon_init(&kl, k[0], k[1], k[2]); which = 7; }
    else if (!strcmp(argv[1], "muff")) { muff_init(&mf, k[0], k[1], k[2]); which = 8; }
    else if (!strcmp(argv[1], "octave")) { ps_params(k); which = 9; }
    else if (!strcmp(argv[1], "id")) which = 0;
    else return 1;
    size_t r;
    while ((r = fread(buf, sizeof(float), 64, stdin)) > 0) {
        if (which == 1) ds1_process(&d, buf, (int)r, 1);
        if (which == 2) gate_process(&g, buf, (int)r, 1);
        if (which == 3) ts808_process(&ts, buf, (int)r, 1);
        if (which == 4) rat_process(&rt, buf, (int)r, 1);
        if (which == 5) fuzz_process(&fz, buf, (int)r, 1);
        if (which == 6) amp_process(&am, buf, (int)r, 1);
        if (which == 7) klon_process(&kl, buf, (int)r, 1);
        if (which == 8) muff_process(&mf, buf, (int)r, 1);
        if (which == 9) ps_process(buf, (int)r, 1);
        fwrite(buf, sizeof(float), r, stdout);
    }
    return 0;
}
