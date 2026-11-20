/* UI speed test (A1): runs once, after the 150th screen update following boot. Pushes known numbers of frames so a
 * stopwatch gives frames/s:  RED screen (20 frames) -> 30 full frames of Mulberry -> GREEN (20) -> 1 Cloudberry
 * frame + 300 tile pushes (32x48) -> BLUE (20) -> memory probe colour (60 frames) -> normal firmware continues.
 * Called instead of the LCD flush from the theme hook; ends by calling the real flush with the same arguments. */
#include "img.h"
typedef void (*flush_fn)(int, int, int, int, u16 *);
typedef void *(*malloc_fn)(unsigned);
#define FLUSH ((flush_fn)0x50BE8)
#define MALLOC ((malloc_fn)0x68D38)
#define SW(v) ((u16)((((v) & 0xFF) << 8) | ((v) >> 8)))

#define buf (*(u16 **)0x2001BC04u)              /* no .bss in a flash-only image: fixed RAM word (test build) */

static void frame(const u16 *img)                 /* 160x128 in 8 strips of 16 rows */
{
    for (int s = 0; s < 8; s++) {
        const u16 *src = img + s * 16 * 160;
        for (int i = 0; i < 16 * 160; i++) buf[i] = src[i];
        FLUSH(0, 159, s * 16, s * 16 + 15, buf);
    }
}

static void solid(u16 c, int frames)
{
    for (int i = 0; i < 16 * 160; i++) buf[i] = c;
    for (int f = 0; f < frames; f++) for (int s = 0; s < 8; s++) FLUSH(0, 159, s * 16, s * 16 + 15, buf);
}

static void tile(const u16 *img, int x, int y)    /* 32x48 patch of img at (x, y), pushed to the same place */
{
    for (int r = 0; r < 48; r++) for (int c = 0; c < 32; c++) buf[r * 32 + c] = img[(y + r) * 160 + x + c];
    FLUSH(x, x + 31, y, y + 47, buf);
}

static void bench(void)
{
    buf = (u16 *)MALLOC(16 * 160 * 2);
    if (!buf) return;
    solid(SW(0xF800), 20);
    for (int i = 0; i < 30; i++) frame(IMG0);
    solid(SW(0x07E0), 20);
    frame(IMG1);
    for (int i = 0; i < 300; i++) { int x = i % 256; x = x < 128 ? x : 255 - x; tile(IMG0, x, 40); }
    solid(SW(0x001F), 20);
    /* free memory probe (test build only, not freed): last colour = largest block we could get:
       WHITE 64 KB, CYAN 32 KB, YELLOW 16 KB, MAGENTA less */
    u16 c = MALLOC(16384) ? 0x07FF : MALLOC(8192) ? 0xFFE0 : 0xF81F;   /* CYAN 16 KB, YELLOW 8 KB, MAGENTA less */
    solid(SW(c), 60);
    frame(IMG0);
}

__attribute__((section(".text.hook"))) void ui_hook(int x1, int x2, int y1, int y2, u16 *px)
{
    volatile unsigned *cnt = (volatile unsigned *)0x2001BC00u;     /* flush counter: a RAM word in an unreferenced gap (test build) */
    FLUSH(x1, x2, y1, y2, px);
    if (*cnt < 1000) { (*cnt)++; if (*cnt == 150) bench(); }
}
