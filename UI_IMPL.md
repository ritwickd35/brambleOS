# UI implementation spec (handoff for the lighter model)

Everything below was worked out on the stock/CFW 1.0.2 MCU app (`cfw/mcu_cfw.dis`, CPU address = file offset +
0x10000, NDS32 V3). Design decisions: `UI_PLAN.md`. Keep this file updated as tasks are done.

## Proven so far (on the pedal)
- Toolchain: NDS32 GCC 13.2 in docker image `pmnds` (`/opt/nds/bin/nds32le-elf-gcc -Os -ffreestanding
  -fno-builtin -nostdlib`, CFW style push25/pop25 is compatible). Example: `ui/hello/` (hello.c + hello.ld).
- Code placement: our code at **flash 0x168000 (CPU 0x178000)**, appended to the MCU section (pad to 0x168000 with
  0xFF). Free and unreferenced up to flash 0x17FFFF (96 KB). Flash 0x180000+ is data (settings, IR/clone slots):
  never write there. MCU section must stay below 0x190000 (effect DB).
- Draw hook: the LCD flush call inside the CFW theme hook at **0x16BD54** (`movi r5,#0x50be8; jral5 r5`) is patched
  to `jal <our hook>; nop16`. Our hook gets `(x1, x2, y1, y2, u16 *px)` (area inclusive, RGB565 byte-swapped:
  write `0x1FF8` for magenta 0xF81F) and must end by calling the LCD flush **0x50BE8** with the same arguments.
  Our pixels come out unchanged by the themes (user-verified: square stayed magenta). Build script logic: see
  build/ui2 in the chat history / `tools` (recreate as `tools/build_ui.py`, base = the release build).

## Screen and drawing
- 160 x 128, RGB565, ST7735S-class. LCD routines: write-cmd 0x50ABC, write-data 0x50B04, set window 0x50B84,
  **flush(x1, x2, y1, y2, px) 0x50BE8** (callable any time from the GUI task to push our own strips).
- Plan: when the current window is ours (home = 7, edit = 6, settings tabs later), the hook ignores the stock
  pixels and fills the requested area from our own renderer (scanline: draw the rows y1..y2 into `px`). For
  animation / live updates, render strips (e.g. 160 x 16) into a malloc'd buffer (malloc 0x68D38, memset 0xDC050)
  and push them with 0x50BE8 from the periodic callback below.
- Existing assets: 107 LVGL-style images (cf 5 = RGB565 + alpha, 3 B/px), exported in `ui/export/` with
  `ui/export/index.json`; descriptor format {u32 cf:5|w:11|h:11, u32 size, u32 data ptr}. Fonts: LVGL fmt_txt, 7
  sizes (`ui/fonts.txt`). We draw our own text with a new small pixel font (to make).

## Windows (WinManager)
- Register: `0x16330(id, enter, exit, cb3)`; switch: 0x162E8. **Current window id: byte at gp-46239
  (gp = 0x2000FA40 -> 0x200045A1)**, also gp-46237.
- Ids: 0 0x23C84, 1 0x28D14, 2 0x22E80, 3 0x2A270, 4 0x27998, 5 0x262E8, **6 edit page 0x1A9B4** (exit 0x1BF60,
  cb3 0x1BF98), **7 home 0x23EFC** (exit 0x23F90, cb3 0x23FCC; cb3 is the periodic update that draws the CPU %),
  8 0x1FF48, 9 0x2118C, 10 0x1DD4C (CFW, settings?), 11 0x24E9C, 12 0x20234, 13 0x238B0, 14 0x23674,
  15 0x1FB30, 16 0x19974. Confirm which one is Settings / tuner / looper by entering them on the pedal with a
  debug build that prints the id in the corner.
- **Periodic tick for our screens: wrap cb3 of windows 6 and 7** (change the pointer in the registration call or in
  the table at gp-16620, 12 bytes per window {enter, exit, cb3}).
- Keys: on enter, each window registers a list `{u32 msg, u32 handler}` with 0x16358(list, n).
  `msg = 2 | key << 8 | event << 16`; keys 0, 1, 2, 0x80, 0x81, 0x82 (0/1 = ◁/▷, 2 = knob push, 0x80/0x82 =
  knob turn, 0x81 = probably ◁+▷), events 1/3/4/5 (press / click / long / repeat - confirm), event 6 only on key 2
  (double-push). For the new edit page: give window 6 our own list (copy + replace handlers).

## Data model (current preset), MCU RAM, M = gp-11100 = 0x2000CEE4
- M+0x08 (u16): current preset index (getter 0x5022C -> 0x4E958). Name: string at gp-11019 (getter 0x50250).
- **Enable bits: u32 at M+0x5F (unaligned), bit = module** (0 NR, 1 FX1, 2 DRV, 3 AMP, 4 IR, 5 EQ, 6 FX2, 7 DLY,
  8 RVB, 9 Clone). Setter 0x4D804.
- **Model index per module: byte at M+0x244+module** (index in that module's effect list).
- **Params: float at M+0x95+32*module+4*p** (p = param index; getter 0x5031C(module, p) -> 0x4DC3C, mapping by
  0x4D5F0). Clone knob 6 = **Cab** (param 5) of our NAM engine.
- Effect DB in RAM: header pointer gp-45556 (same format as the firmware DB section: +0x13 group count), group
  lists gp-13924; 0x18440/0x18648(group, index) return the record (format: tools/dbrec.py; title string at
  16 + 24 * knob count).
- Chain order: probably at M+0x63.. (0x4EA04/0x4EA18 read M+0x63/0x64) - confirm.
- Model API with change notify: wrappers 0x50200-0x50500 (call 0x4CA58 to notify the DSP / app).

## NAM (own clone engine, firmware build/clone5)
- Clone mode = AMP bit + Clone bit (module 9) on; clone slot = fx id 0x0F000000 + slot.
- Clone knobs: Gain, VOL, Bass, Middle, Treble, **Cab** (0 = capture's own cab, 1-15 factory cab index 0-14,
  16-25 User IR 1-10).
- The real IR block (module 4) must stay OFF in NAM presets (our engine + IR block = silence). The screen shows a
  substitute IR block driven by the Cab knob. Capture type (amp only / amp + cab) = clone file 0x20 (u32 type);
  own cab present = 0x28 (u32 has_fir). Clone slot data pointer: kernel side; MCU side has the clone list (names).

## Task list for the lighter model (in order; flash only with the user present)
1. `tools/build_ui.py`: base build (release + clone5) + our C code at 0x168000 + the 0x16BD54 patch + cb3 wrappers.
2. Pixel font (5x7 and 8x12) as C arrays; text draw into a strip buffer.
3. Gear pixel art: small 28x24 and large ~42x36 for every effect in the lineup (drives, 16 amps, NAM, cabs, EQ,
   FX1/FX2, delays, reverbs, NR). PNG contact sheet `ui/art/contact.png` for the user to approve **before**
   converting to C arrays (RGB565 + 1-bit mask, palette per sprite to save flash).
4. Home screen renderer (window 7): header, 2 x 5 squares in chain order with lit/dim art + labels, thin load
   bars; NAM: AMP square "NAM", IR square = substitute (Cab knob). Debug build first: print the window id.
5. Edit page (window 6): block strip, big art + model + ON badge + tone curve, 4 knob rings; new key list.
6. Settings pages (one list per tab, previews), Level / I/O / USB / MIDI / G-EQ / Display / BT / Boot.
7. Load bars: CPU % (value used by the stock home cb3 near 0x24174); engine load needs a DSP-side message (later).
8. Animations test (frame time on screen), `Animations on/off` setting.
9. Final: every window, long soak; then the full guitar-DI test of all effects (needs the jack, last).

## Added 2026-11-21: themes, "Berry" look, animations, Tuner / Recording / Drum pages

### Themes (CFW)
- Theme index: **byte 0x2001BB88** (0 = Default; 1..5 = Amber CRT, Tube Amp, Synthwave, Stage HC, Game Boy). The CFW
  recolours every flushed pixel through a lookup table when it is not 0 (hook 0x16BD3E); our pixels are drawn
  after that step, so **we pick our own palette from the theme byte** (user-verified: our colours are not changed).
- Stock UI colours: palette lookup 0x2C1D0(index) -> RGB565 from a table at gp-48236 (208 callers).
- Design rule: all our art is **indexed colour (4 bpp, 16-colour palettes)** -> one palette set per theme
  (6 x 16 colours), art stored once. Saves flash (half of RGB565) and makes theme support a palette swap.

### Pages to redesign (window ids from the image references; confirm with the window-id debug build)
- **Tuner = window 3** (0x2A270 / exit 0x2B41C / cb3 0x2B458): images 22-39 (cent bars, 9 px wide), 30/31 and
  38/39 (33x21 triangles), "A4 = %dHz", "MUTE".
- **Recording / looper = window 9** (0x2118C / 0x222AC / 0x222FC): images 9/10 (72x26 record-play and
  stop-clear buttons), 74/75 (Pre/Post).
- **Drum machine = window 5** (0x262E8 / 0x266EC / 0x26728): images 17-21 (play/stop, type list, volume,
  metronome), 70 (74x44 big play), 93.
- How to get their live values without decoding each data path: **observe the stock widgets**. The stock pages
  set their widgets through a few setters: image source 0x479B8, label printf 0x48CD0, hide/show 0x47998,
  position/size 0x335CC / 0x335E8, colour 0x2C1D0 (object lookup 0x337B0). Hook these (jump stubs) and keep the
  last value per object id; our renderer draws from that (e.g. tuner: which cent-bar image is lit + the note
  label text; looper: state image + time label; drum: play state, pattern name, VOL, BPM labels).
  Stock pages keep working underneath; our hook only replaces the pixels for windows we redesign.

### Animations: rules and measurement
- Allowed: preset name slide-in (4 frames), block on/off fade (3 frames), selection highlight move (3 frames),
  knob ring sweep to the new value (3 frames), model picture cross-fade (4 frames), tuner needle smoothing
  (continuous, small area), looper progress, drum beat pulse. Each <= 0.3 s, never blocks a key press (keys are
  handled first, an animation in flight jumps to its end state on a new key).
- Cost: redraw only the changed rectangle (a 32x48 square = 3 KB of pixels, a full screen = 40 KB).
- Must be measured first (task A1 below): the SPI speed and our draw time per frame are unknown. Candidate tick
  counters for timing: gp getters 0x436B0 (gp-44980, 39 callers) and 0x348C0 - check which one counts ms.
- Setting "Animations: on/off" in Display.

### "Berry" look (to be approved with the art)
- Base: deep berry gradient background (plum -> wine, very dark, 2-3 steps of vertical gradient, no noise),
  blocks as rounded "drupe" tiles with a soft top highlight (berry skin sheen: 1-px light rim at the top-left,
  slightly darker bottom), selection = a thin glowing rim, "on" accent = leaf green, warnings = berry red.
- Gear art keeps the real gear colours (green TS808 etc.) but gets the same light model: 1-px highlight top-left,
  1-px shade bottom-right, subtle 2-step gradient on large faces (amp panels, pedal bodies).
- Per theme a palette variant: Default = berry; Amber CRT / Game Boy / Synthwave / Tube Amp / Stage HC = the same
  art in that theme's colours (palette swap), so themes keep working.

### New tasks (light, in order; A1 first)
- A1 Animation/speed test build: moves a 32x48 tile across the home screen, prints frames/s and ms per
  frame (tick counter), plus the current window id. Flash with the user; decide the frame budget from it.
- A2 Widget-observer hooks for windows 3, 5, 9 (log values into a small RAM table; show them in a debug overlay).
- A3 Berry palettes (6 themes x 16 colours) + mock-ups of home, edit, settings, tuner, recording, drum pages
  (PNG, 160x128 and 4x) for the user's approval, together with the gear art contact sheet.

### Berry style at 160x128 RGB565 - checked (ui/berry/feasibility.py, _1x/_4x.png)
- Dark gradients band (only ~5-8 RGB565 steps in plum/wine): use a 2x2 ordered dither (one 565 step).
- Tiles 28x24: corner radius 2-3 px; sheen = 1-px light rim top-left + 1-px dark rim bottom-right; no inner
  gradient on small tiles (invisible). Inner gradients only on art >= 40 px.
- Selection glow = 1-px bright rim + 1-px dim outer rim (2 px of "glow" reads as a box).
- Tiles stay dark plum; colour comes from the gear art; on = bright rim + full-colour art, off = dimmed art.

### Status 2026-11-21 ~02:55
- Themes decision: the community firmware's 6 themes are REPLACED by Berry themes (Mulberry, Elderberry, Lingonberry,
  Blackcurrant, Jamun, Cloudberry [light]). Our redesigned screens use our palettes (ui/berry/pages.py THEMES dict:
  add the other four). Stock screens we do not redesign are recoloured by the CFW lookup tables (code ~0x16BD3E:
  byte table 0x17688C, halfword table 0x170C0C, 0x1280 bytes per theme): TODO rewrite those tables with berry ramps.
- Soft style (anti-aliased shapes, r=5 tiles, two-step rounded selection ring, dithered gradient) approved in
  principle; mock-ups of Home, Edit, Tuner, Recording, Drums, Settings for Mulberry + Cloudberry:
  ui/berry/pages/sheet_Mulberry.png, sheet_Cloudberry.png (generator ui/berry/pages.py). Known mock nits: drum "BPM"
  label overlaps the big number, edit-page curve label.
- Docker image pmnds (NDS32 gcc) was lost when Docker restarted; rebuilding in container pmgcc3 (ui/build_gcc.sh,
  ~1 h, -j1; output in ui/nds/bin when ui/nds/DONE exists). tools/build_ui.py is ready (uses ui/nds + pmre).
- Speed test A1 is written (ui/speed/speed.c, img.h): after 150 flushes it shows RED x20 frames, 300 full frames,
  GREEN x20, 2000 tile pushes, BLUE x20, so a stopwatch gives frames/s. No tick counter found (searched the
  MCU for FreeRTOS tick: none obvious) -> stopwatch method. Build: python3 tools/build_ui.py build/clone5 ui3 ui/speed.
  Flash with the user present (note: every flash resets presets from the image; P08 restore needed).

### Resource budget (checked 2026-11-21) - must stay within these
- **Flash for our UI: 79.8 KB, measured** (flash 0x168000 .. 0x17BF50). The updater accepts an MCU section up to
  0x17BF50 bytes (tested: +32/64/72/76/80 KB padding OK) and REFUSES 0x17C1B4 (NAK at the section header); the
  limit is probably 0x17C000. (The earlier 96 KB figure was wrong: the pad probes are tools/size_probe.py.) Estimate: code ~35 KB, fonts ~7 KB (7 px + 10 px text, 2 bpp
  anti-aliased; big digits/note letters 2 bpp), gear art ~57 KB raw -> **must be compressed** (RLE on 4 bpp,
  transparent background compresses well, target ~38 KB) => ~80 KB total, ~15 KB margin.
  Art plan: 126 effects + 16 cabs + NAM. Small 28x24 4 bpp (336 B) as ~70 shared shapes (effect families) + a
  16-colour palette per effect (32 B); large 42x36 (756 B) only for drives (7), amps (16), NAM, cab sizes (4);
  other blocks use a family large picture (~10). Themes = run-time palette transform (no stored palettes per theme).
  Reserve option if it does not fit: reclaim stock images used only by screens we replace (19 block icons 33x47 =
  86 KB) - only after all those screens are ours.
- **RAM**: no frame buffer (40 KB would not fit safely). Strip renderer: one 160x16 buffer (5 KB) from malloc,
  widget-observer table < 1 KB, animation state < 256 B. The speed test probes free heap (last colour: white
  64 KB / cyan 32 KB / yellow 16 KB / magenta less).
- **CPU**: shapes drawn procedurally (rounded rects, rings, bars, gradient + dither) per changed rectangle only;
  full-screen redraw only on screen change. Frame time measured by the speed test before animations are built.
- **Readability**: minimum text 7 px (the 6 px hint lines in the mock-ups are too small: make them 7 px or drop).
