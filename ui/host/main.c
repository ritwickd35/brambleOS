/* Host harness: renders pages with the same C code as the pedal. usage: ui_host <theme 0|1> <page> <out.rgb565> [strips] */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "../src/pages.h"
int main(int argc, char **argv)
{
    int th = atoi(argv[1]); static u16 px[160 * 128]; model_t m; memset(&m, 0, sizeof m);
    strcpy(m.name, "UKInvasion"); m.preset = 8; m.edited = getenv("EDITED") ? atoi(getenv("EDITED")) : 1; m.vol = 100; m.bt = 1; m.bat = 80; m.cpu = 28; m.eng = getenv("ENG") ? 77 : -1; m.bpm = 120; m.sel = -1; m.nam = 0;
    u8 on[9] = {0, 0, 1, 1, 1, 0, 0, 1, 1}; memcpy(m.on, on, 9); for (int i = 0; i < 9; i++) m.order[i] = i; m.chg = 1;
    strcpy(m.mname, "JCM800"); strcpy(m.brand, "Marshall 2203"); m.nk = 6; const char *kn[6] = {"GAIN", "BASS", "MID", "TREB", "PRES", "VOL"}; int kv[6] = {72, 55, 60, 48, 40, 65};
    for (int i = 0; i < 6; i++) { strcpy(m.kn[i], kn[i]); m.kv[i] = kv[i]; m.kmx[i] = 100; m.kraw[i] = kv[i]; } if (getenv("BOOST")) { m.nk = 3; strcpy(m.kn[0], "Gain"); strcpy(m.kn[1], "+3dB"); strcpy(m.kn[2], "Brig"); m.kmx[1] = m.kmx[2] = 1; m.kraw[1] = 1; m.kraw[2] = 0; m.kv[1] = 100; m.kv[2] = 0; } m.ksel = 0; m.erow = getenv("ROW") ? atoi(getenv("ROW")) : 0; m.ecol = getenv("COL") ? atoi(getenv("COL")) : 0; m.eopen = getenv("OPEN") ? 1 : 0; m.nav = getenv("NAV") ? 1 : 0; m.ekind = getenv("KIND") ? atoi(getenv("KIND")) : 0; m.ksel = getenv("KSEL") ? atoi(getenv("KSEL")) : 0; m.note = 4; m.octave = 2; m.cents = 4; m.hz10 = 827; m.a4 = 440; m.mute = 1;
    void (*pg)(const model_t *) = !strcmp(argv[2], "edit") ? page_edit : !strcmp(argv[2], "tuner") ? page_tuner : !strcmp(argv[2], "rec") ? page_rec :
        !strcmp(argv[2], "drum") ? page_drum : (!strcmp(argv[2], "settings") || !strcmp(argv[2], "level")) ? page_settings : !strcmp(argv[2], "dialog") ? page_dialog : page_home;
    m.rstate = 1; m.rtime10 = 127; m.rpost = 1; m.rvol = 100; m.pvol = 80; m.rsel = getenv("SELI") ? atoi(getenv("SELI")) : 1; m.dplay = 1; m.dvol = 70; m.dsel = getenv("SELI") ? atoi(getenv("SELI")) : 1; strcpy(m.dtype, "Rock 1"); m.bpm = 120;
    { static const char *lab[5], *val[5], *tb[5]; static int kind[5], num[5];
      if (!strcmp(argv[2], "level")) { static const char *l2[3] = {"Input Level", "Output Level", "Clip warning"}, *v2[3] = {"+3 dB", "0 dB", ""}; static const int k2[3] = {3, 3, 2}, n2[3] = {62, 50, 1}; static const char *t2[5] = {"Level", "G-EQ", "USB", "Boot", "Display"};
        for (int i = 0; i < 3; i++) { lab[i] = l2[i]; val[i] = v2[i]; kind[i] = k2[i]; num[i] = n2[i]; } for (int i = 0; i < 5; i++) tb[i] = t2[i]; m.stitle = "Level"; m.sn = 3; m.spreview = 2; m.slevel = 70; m.tsel = 0; m.spages = 1; m.spage = 1; }
      else { static const char *l1[3] = {"Theme", "Controls", "Brightness"}, *v1[3] = {"Mulberry", "Push next", ""}; static const int k1[3] = {0, 0, 1}, n1[3] = {0, 0, 85}; static const char *t1[5] = {"USB", "Boot", "Display", "BT", "MIDI"};
        for (int i = 0; i < 3; i++) { lab[i] = l1[i]; val[i] = v1[i]; kind[i] = k1[i]; num[i] = n1[i]; } for (int i = 0; i < 5; i++) tb[i] = t1[i]; m.stitle = "Display"; m.sn = 3; m.spreview = 1; m.slevel = th == 1 ? 1 : 0; m.tsel = 2; m.spages = 2; m.spage = 1; }
      m.ssel = getenv("SELI") ? atoi(getenv("SELI")) : 0; for (int i = 0; i < 5; i++) { m.slab[i] = lab[i]; m.sval[i] = val[i]; m.skind[i] = kind[i]; m.snum[i] = num[i]; m.tabs[i] = tb[i]; } }
    int strips = argc > 4 ? atoi(argv[4]) : 1;                       /* render in N strips like the pedal does (must be identical) */
    for (int s = 0; s < strips; s++) { int y1 = s * 128 / strips, y2 = (s + 1) * 128 / strips - 1; gfx_begin(0, 159, y1, y2, px + y1 * 160, &THEMES[th]); pg(&m); }
    FILE *f = fopen(argv[3], "wb"); fwrite(px, 2, 160 * 128, f); fclose(f); return 0;
}
