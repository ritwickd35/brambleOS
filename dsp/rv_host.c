/* rv_host <voice 0..8> <p0..p7> < stereo f32 > stereo f32 (interleaved L,R at 44.1 kHz) */
#include <stdio.h>
#include <stdlib.h>
#include "reverb.h"
extern const struct rv_voice RV_VOICES[9];
int main(int c, char **v)
{
    static float buf[128]; float p[8] = {0}; int vi = atoi(v[1]);
    for (int i = 2; i < c && i < 10; i++) p[i - 2] = (float)atof(v[i]);
    rv_set(&RV_VOICES[vi], p); size_t r;
    while ((r = fread(buf, sizeof(float), 128, stdin)) > 0) { rv_process(&RV_VOICES[vi], buf, (int)(r / 2)); fwrite(buf, sizeof(float), r, stdout); }
    return 0;
}
