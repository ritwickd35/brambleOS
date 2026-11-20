#include <stdio.h>
#include <stdlib.h>
#include "delay.h"
extern const struct dl_voice DL_VOICES[5];
int main(int c, char **v)
{
    static float buf[128]; float p[8] = {0}; int vi = atoi(v[1]);
    for (int i = 2; i < c && i < 10; i++) p[i - 2] = (float)atof(v[i]);
    dl_set(&DL_VOICES[vi], p); size_t r;
    while ((r = fread(buf, sizeof(float), 128, stdin)) > 0) { dl_process(&DL_VOICES[vi], buf, (int)(r / 2)); fwrite(buf, sizeof(float), r, stdout); }
    return 0;
}
