#ifndef PAGES_H
#define PAGES_H
#include "gfx.h"
typedef struct {
    int preset; char name[24]; int edited;          /* current preset 1..100, name, unsaved changes */
    int hfocus;                                                             /* home: what the encoder controls: 0 Bluetooth, 1 volume, 2 preset */
    int vol, bt, bat, chg;  /* -1 = not known (element not drawn) */                         /* master volume 0..100, Bluetooth on, battery 0..100, charging */
    int cpu, eng, bpm;                              /* DSP load %, engine load %, tempo */
    u8 on[9];                                       /* NR FX1 DRV AMP IR EQ FX2 DLY RVB : block enabled */
    u8 order[9];                                    /* chain order: order[slot] = block (0..8) */
    int sel; int nam;                               /* selected block (0..8); AMP block is a NAM clone */
    /* edit page (selected block = sel) */
    char mname[20], brand[24]; int nk; char kn[8][6]; int kv[8], kmx[8], kraw[8]; int ksel;   /* kv = 0..100 %, kmx = range top, kraw = raw value */   /* model, maker/original, knobs 0..100 */
    /* tuner */
    int glide; float gx, gy, gw, gh, gr;                                     /* edit page: the highlight is drawn at this rectangle while it glides to the next item */
    int hg; float hgx, hgy, hgw, hgh, hgr;                                   /* home: the same for the focus ring */
    float hlx, rgx, rgy; int pulse;                                          /* animation overrides (0 = none): knob highlight x, chain ring x/y, on/off pulse 1..3 */
    int nav;                                                                 /* edit page navigation: 0 push = next item, 1 turn = select / push = edit */
    int erow, ecol, eopen; int ekind;                                         /* ekind: 0 knob (ksel), 1 on/off, 2 model, 3 mode */                                                   /* edit page cursor: row (0 = block, 1.. = knob rows), column, open */
    /* recording / looper */
    int rstate, rtime10, rpost, rvol, pvol, rsel;                            /* rstate 0 empty, 1 rec, 2 play, 3 stop; time in 0.1 s */
    /* drum machine */
    int dplay, dvol, dsel; char dtype[16];
    /* settings: one list page */
    int spreview, slevel, sicon;                                             /* settings: bottom preview (0 none, 1 theme swatches, 2 input meter), live level 0..100 */
    const char *stitle; int spage, spages, ssel, sn; const char *slab[6]; const char *sval[6]; int skind[6], snum[6];   /* kind 0 text, 1 bar, 2 switch */
    const char *tabs[5]; int tsel;
    char dbg[24];                                                            /* debug text (edit page probe), empty = none */
    int note, octave, cents, hz10, a4, mute;                                 /* note 0..11 (C..B), -1 = no signal; hz x10 */
} model_t;
void page_home(const model_t *m);
void page_edit(const model_t *m);
void edit_item_rect(int kind, int ks, float *r);                              /* highlight rectangle of an edit-page item: x, y, w, h, radius */
void home_focus_rect(const model_t *m, int f, float *r);                      /* focus ring of the home page: 0 Bluetooth, 1 volume, 2 preset */
void page_tuner(const model_t *m);
void page_rec(const model_t *m);
void page_drum(const model_t *m);
void page_settings(const model_t *m);
void page_dialog(const model_t *m);
void sprite(int kind, float x, float y, int lit, int variant);
#endif
