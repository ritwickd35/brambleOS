/* Our reverb menu entries (voices). Knob indices follow each slot's stock DB record (tools/dbrec.py). */
#include "reverb.h"
#define ER0 {0, 0, 0, 0, 0, 0}
const struct rv_voice RV_VOICES[9] = {
 /* 0 Room (Room slot): Mix Decay HC LC */
 {0.35f, 0.20f, 1.5f, 0.55f, 0.65f, 0.f, 0.3f, 1.0f, 3.f, 0.9f, 1.165f, 0.f, 0.f,
  {2.1f, 3.4f, 5.3f, 7.9f, 11.2f, 14.6f}, {0.5f, 0.45f, 0.35f, 0.3f, 0.22f, 0.18f}, 0, 1, -1, -1, 2, 3},
 /* 1 Chamber (Air slot): Mix Decay Damp HC LC */
 {0.7f, 0.5f, 3.0f, 0.6f, 0.7f, 0.f, 0.4f, 0.8f, 8.f, 0.9f, 2.309f, 0.f, 0.f,
  {4.3f, 6.9f, 10.4f, 15.1f, 21.7f, 27.9f}, {0.3f, 0.27f, 0.22f, 0.18f, 0.14f, 0.1f}, 0, 1, 2, -1, 3, 4},
 /* 2 Hall: Mix Decay HC LC */
 {1.3f, 0.8f, 6.0f, 0.55f, 0.7f, 0.5f, 0.6f, 0.7f, 20.f, 1.0f, 2.972f, 0.f, 0.f,
  {12.f, 17.f, 23.f, 29.f, 37.f, 46.f}, {0.3f, 0.28f, 0.24f, 0.2f, 0.16f, 0.12f}, 0, 1, -1, -1, 2, 3},
 /* 3 Church: Mix Decay HC LC */
 {2.2f, 1.5f, 10.0f, 0.45f, 0.75f, 0.6f, 0.5f, 0.5f, 35.f, 1.0f, 4.833f, 0.f, 0.f,
  {21.f, 33.f, 47.f, 61.f, 79.f, 97.f}, {0.22f, 0.2f, 0.17f, 0.14f, 0.11f, 0.08f}, 0, 1, -1, -1, 2, 3},
 /* 4 Plate (Plate 1 slot): Mix Decay HC LC */
 {0.9f, 0.6f, 6.0f, 0.9f, 0.75f, 0.7f, 0.3f, 0.9f, 0.f, 1.0f, 3.208f, 0.f, 0.f, ER0, ER0, 0, 1, -1, -1, 2, 3},
 /* 5 Shimmer (Plate 2 slot): Mix Decay Damp HC LC */
 {1.4f, 1.5f, 10.0f, 0.7f, 0.7f, 0.5f, 0.6f, 0.6f, 15.f, 1.0f, 4.279f, 0.f, 0.35f, ER0, ER0, 0, 1, 2, -1, 3, 4},
 /* 6 Spring: Mix Decay HC LC */
 {0.5f, 1.0f, 4.0f, 0.5f, 0.5f, 0.f, 0.2f, 1.0f, 0.f, 0.6f, 2.583f, 0.6f, 0.f, ER0, ER0, 0, 1, -1, -1, 2, 3},
 /* 7 Dream: Mix Decay Damp Mod HC LC */
 {1.4f, 1.5f, 10.0f, 0.4f, 0.7f, 0.6f, 1.2f, 0.5f, 15.f, 1.0f, 4.452f, 0.f, 0.f, ER0, ER0, 0, 1, 2, 3, 4, 5},
 /* 8 Ambient: Mix Mod Decay Tone Damp LC */
 {1.6f, 2.0f, 15.0f, 0.5f, 0.75f, 0.7f, 1.5f, 0.6f, 10.f, 1.0f, 7.108f, 0.f, 0.f, ER0, ER0, 0, 2, 4, 1, 67, 5},
};
