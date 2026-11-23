/* Berry UI renderer: immediate-mode, draws into the pixel buffer of one flush rectangle (no frame buffer).
 * Same code runs on the Mac (ui/host) and on the pedal (NDS32, freestanding). Pixels: RGB565, panel byte order. */
#ifndef GFX_H
#define GFX_H
typedef unsigned short u16; typedef unsigned char u8;
typedef struct { u8 r, g, b; } rgb_t;
typedef struct { rgb_t bg0, bg1, tile, tile_off, text, sub, hi, ring, on, warn, track, ink; u8 dark; } theme_t;
#include "font_data.h"

void gfx_begin(int x1, int x2, int y1, int y2, u16 *px, const theme_t *t);   /* area inclusive */
const theme_t *gfx_theme(void);
void gfx_bg(void);                                                          /* dithered vertical gradient */
void gfx_tray(float x, float y, float w, float h, float x2, float y2, float w2, float h2, float r, rgb_t c, float a);
void gfx_rrect(float x, float y, float w, float h, float r, rgb_t c, float a);
void gfx_rring(float x, float y, float w, float h, float r, float th, rgb_t c, float a);
void gfx_disc(float cx, float cy, float r, rgb_t c, float a);
void gfx_arc(float cx, float cy, float r, float th, float a0, float a1, rgb_t c, float a);   /* degrees, 0 = right, clockwise */
void gfx_tri(float x0, float y0, float x1, float y1, float x2, float y2, rgb_t c, float a);
void gfx_bar(float x, float y, float w, float h, float v, rgb_t c);
void gfx_tile(float x, float y, float w, float h, int lit, int sel, float r);
float gfx_sin(float deg);
void gfx_led(float x, float y, int on);
int  gfx_text_w(const font_t *f, const char *s);
void gfx_text(float x, float y, const char *s, const font_t *f, rgb_t c, const char *anchor, float a);
void gfx_text_solid(float x, float y, const char *s, const font_t *f, rgb_t c, const char *anchor, float a);   /* heavier anti-aliasing: clearer on this screen */
void gfx_pill(float x, float y, float w, float h, const char *s, const font_t *f, int on, rgb_t fill);
rgb_t rgbf(rgb_t a, rgb_t b, float t);                                      /* mix */
extern const theme_t THEMES[];
#endif
