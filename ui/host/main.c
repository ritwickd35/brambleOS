/* Host harness: renders pages with the same C code as the pedal. usage: ui_host <theme 0|1> <page> <out.rgb565> [strips] */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "../src/pages.h"
int main(int argc, char **argv)
{
    int th = atoi(argv[1]); static u16 px[160 * 128]; model_t m; memset(&m, 0, sizeof m);
    strcpy(m.name, "UKInvasion"); m.preset = 8; m.edited = getenv("EDITED") ? atoi(getenv("EDITED")) : 1; m.vol = 100; m.bt = 1; m.bat = 80; m.cpu = 28; m.eng = 77; m.bpm = 120; m.sel = -1; m.nam = 0;
    u8 on[9] = {0, 0, 1, 1, 1, 0, 0, 1, 1}; memcpy(m.on, on, 9); for (int i = 0; i < 9; i++) m.order[i] = i; m.chg = 1;
    strcpy(m.mname, "JCM800"); strcpy(m.brand, "Marshall 2203"); m.nk = 6; const char *kn[6] = {"GAIN", "BASS", "MID", "TREB", "PRES", "VOL"}; int kv[6] = {72, 55, 60, 48, 40, 65};
    for (int i = 0; i < 6; i++) { strcpy(m.kn[i], kn[i]); m.kv[i] = kv[i]; } m.ksel = getenv("KSEL") ? atoi(getenv("KSEL")) : 0; m.note = 4; m.octave = 2; m.cents = 4; m.hz10 = 827; m.a4 = 440; m.mute = 1;
    void (*pg)(const model_t *) = !strcmp(argv[2], "edit") ? page_edit : !strcmp(argv[2], "tuner") ? page_tuner : page_home; if (pg == page_edit) { m.sel = getenv("SEL") ? atoi(getenv("SEL")) : 3; if (getenv("OFF")) m.on[m.sel] = 0; }
    int strips = argc > 4 ? atoi(argv[4]) : 1;                       /* render in N strips like the pedal does (must be identical) */
    for (int s = 0; s < strips; s++) { int y1 = s * 128 / strips, y2 = (s + 1) * 128 / strips - 1; gfx_begin(0, 159, y1, y2, px + y1 * 160, &THEMES[th]); pg(&m); }
    FILE *f = fopen(argv[3], "wb"); fwrite(px, 2, 160 * 128, f); fclose(f); return 0;
}
