/* half lp_lo lp_hi hp sat in_sat wow_hz wow_ms flut_hz flut_ms haas_ms wet_gain fb_max | Mix Time F.Back Tone */
#include "delay.h"
const struct dl_voice DL_VOICES[5] = {
 /* 0 Digital (Pure slot): clean, full range, wide */
 {0.f, 3000.f, 18000.f, 40.f, 0.f, 0.f, 0.f, 0.f, 0.f, 0.f, 11.f, 1.0f, 0.95f, 0, 1, 2, 5}, 
 /* 1 Slap: short, slightly warm, wide */
 {0.f, 2500.f, 9000.f, 80.f, 1.2f, 0.f, 0.f, 0.f, 0.f, 0.f, 7.f, 1.0f, 0.8f, 0, 1, 2, 5},
 /* 2 EP-3 (Mag slot): preamp, wow and flutter, darkening tape repeats */
 {1.f, 1500.f, 4500.f, 90.f, 1.6f, 1.4f, 0.55f, 0.2f, 6.5f, 0.05f, 9.f, 1.1f, 1.0f, 0, 1, 2, 5},
 /* 3 Analog (BBD): dark, soft saturation, slow chorus-like modulation */
 {1.f, 1400.f, 4200.f, 60.f, 1.3f, 0.f, 0.35f, 0.25f, 0.f, 0.f, 9.f, 1.1f, 1.0f, 0, 1, 2, 5},
 /* 4 Echo: classic warm single echo */
 {1.f, 3500.f, 3500.f, 70.f, 1.2f, 0.f, 0.4f, 0.12f, 5.f, 0.03f, 6.f, 1.0f, 0.95f, 0, 1, 2, -1},
};
