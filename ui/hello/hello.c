/* UI toolchain proof: draws a small marker in the top-right corner of every frame, then hands the pixels to the
   original flush path (CFW theme hook trampoline 0x16BB60 -> LCD flush). Called instead of that trampoline from
   the stock flush callback @0x4A9CC with (x1, x2, y1, y2, pixels) - the area is inclusive, RGB565. */
typedef unsigned short u16;
typedef void (*flush_fn)(int, int, int, int, u16 *);
#define ORIG ((flush_fn)0x50BE8)          /* the LCD flush itself: we run after the theme step */
#define MX0 150
#define MX1 155
#define MY0 2
#define MY1 7

void ui_hook(int x1, int x2, int y1, int y2, u16 *px)
{
    int w = x2 - x1 + 1;
    for (int y = MY0; y <= MY1; y++) {
        if (y < y1 || y > y2) continue;
        for (int x = MX0; x <= MX1; x++) {
            if (x < x1 || x > x2) continue;
            px[(y - y1) * w + (x - x1)] = 0x1FF8;      /* magenta (byte-swapped 0xF81F) */
        }
    }
    ORIG(x1, x2, y1, y2, px);
}
