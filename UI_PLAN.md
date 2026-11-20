# UI work plan (screen controller firmware)

Goal (decided with the user): main screen shows the whole signal chain; smaller preset name; edit page with a
smaller block row and a bigger top panel; a picture of the effect in use instead of its name (monochrome line art
tinted with the block colour; modelled gear drawn as it really looks); two load bars (DSP and audio engine)
instead of the chip icon + %; brightness and English/Chinese in Settings.

## What we know (reverse engineering status)

| Topic | Status |
|---|---|
| Chip, code | MVSilicon BP10, Andes NDS32 V3 core; app runs at CPU 0x10000 (= file offset + 0x10000); FreeRTOS-style tasks |
| Recovery | Bootloader at CPU 0x0000–0xFFFF is not part of updates; button-combo update mode always works (used today) |
| Tools | NDS32 binutils in the `pmre` docker image (`/opt/nds/bin/nds32le-elf-as`, objdump); no C compiler yet |
| Free flash | App (CFW) ends at file 0x167F50; next section at 0x190000 → ~160 KB free (not yet proven unused at runtime) |
| Windows / keys | WinManager: window table, per-window key maps, message format (§18) |
| Language | Two string tables, set_lang, boot overwrites from factory config; 2-patch English fix proven on stock (§11, §17) |
| Brightness | Setter/getter/driver known (PWM channel 4), saved in settings +0x0F (§19); no menu item yet |
| Block labels | Drawn as images, not text (§16): the "NR/FX1…" boxes and the big block icons are bitmaps |
| Images | Bitmap-like regions found at file 0xD0000–0x104000 and 0x120000 (few distinct 16-bit values = RGB565 palette art); one 148×48 GIF (boot) |
| CPU % | `%d%%` string present; value most likely sent by the DSP (it reacts to audio-engine overload); path not traced |
| Screen | **160 × 128 RGB565**, ST7735S-class (NOTES §49); LVGL-style images (107 exported to ui/export, ui/contact.png), 7 fonts (10–24 px + 49 px) |

## Unknowns that block the work (in order)

1. Screen size, pixel format, and the low-level draw calls (fill rect, draw bitmap, draw text, font sizes).
2. Where the main-screen and edit-page layouts are drawn (which window functions, which coordinates).
3. Image table format (how a bitmap is referenced: address, width, height, palette).
4. How the CPU % arrives from the DSP (message type), to add the second value (engine load).
5. Whether the ~160 KB tail of the MCU section is really free at runtime.

## Plan

Each step ends with something checked on the pedal. All MCU tests run while you watch the screen; the overnight
audio test is paused during them (`tools/night_ctl.sh pause|resume`).

### Phase 0 — groundwork (offline, no flashing)
- Get an NDS32 C compiler running (GCC 4.9 Andes build in docker; fallback: hand-written assembly with the
  binutils we have). Build a "hello" function and check the call convention against existing code.
- Trace the LCD init sequence → controller type, resolution, pixel format; find fill-rect / blit / text routines
  (they are called hundreds of times with small constant arguments).
- Map the image table: find the pointers used when the main screen draws the "NR" box; decode width/height/format;
  export all UI images to PNGs (`ui/export/`) so we can see every asset.

### Phase 1 — smallest visible change (1 flash, proves the toolchain)
- Brightness + English as Settings items, using the known setters and an existing settings list window.
  Low risk, useful, and it proves: patching, adding a menu entry, saving a setting across reboots.

### Phase 2 — load bars
- DSP side: add the audio-engine load (we already read its counter) to the message that carries CPU %.
- MCU side: replace the chip icon + % by two horizontal bars (green < 70 %, amber < 90 %, red), redrawn a few times
  per second. Verified with a light preset (both low) and RAT+amp+cab (engine bar high).

### Phase 3 — icons (preview first, no firmware change)
- Generate the icon set on the Mac from templates (1-bit line art, 48×32 and 24×20; real-gear silhouettes for
  drives/amps/cabs, symbolic pictures for the other effects); a PNG contact sheet for your approval.
- Pack as 1-bit bitmaps (~37 KB) with an index by effect id into the free MCU flash; draw with the block colour.

### Phase 4 — layouts
- Main screen: smaller preset-name font, 10-block chain row in signal order with small icons (on = colour,
  off = dim). Try one row of 10 and two rows of 5 on the real screen; you pick.
- Edit page: shrink the block row, enlarge the top panel, show the big icon of the selected effect in place of
  the name text (name stays as a small caption).

### Phase 5 — polish and soak
- Check every window still works (menus, tuner, looper, drum, BT, USB), long-press/back behaviour unchanged,
  no flicker or slow redraws; a 1-hour screen-on soak.

## Risks and safety
- A bad MCU build can freeze the screen/menus; the bootloader and button-combo update mode stay intact, so recovery
  is always possible (needs you at the pedal). Only flash MCU tests when you are there.
- Font/size changes may not fit the existing layout code; fallback is drawing those regions ourselves.
- Icons take flash space; 1-bit art keeps it at ~37 KB of the ~160 KB free.

## Effort estimate
Phase 0: 3–5 h (mostly offline). Phase 1: 1–2 h. Phase 2: 2–3 h. Phase 3: 2–3 h + your review. Phase 4: 4–6 h.
Phase 5: 1 h + soak.

## Decisions (2026-11-20, from the user)

**Home screen** (160 × 128):
```
 header  ~16 px  "P08  UKInvasion*" + battery   (* = edited, not saved)
 blocks  2 rows x 5 squares, ~32 x 48 px each: miniature of the gear shown on the edit page (~28 x 24, changes
         with the model; full colour = on, greyed = off) + block-type label below (NR, FX1, DRV, AMP / NAM, IR,
         EQ, FX2, DLY, RVB) in a new ~7 px pixel font; squares follow the real chain order
 square 10: free (placeholder BPM; alternatives: empty, NAM slot name) - to decide
 bars    ~6 px thin row: DSP and ENG load bars (made thinner so the header gets the space)
```
**Edit page** (proposal, accepted as direction; button events to be confirmed in firmware):
- top ~18 px: all blocks as small icons in chain order, selected outlined; middle ~50 px: big gear picture,
  model name, "based on", ON badge; bottom ~60 px: up to 4 knob rings + values, page dots.
- turn = change the highlighted control (starts on the first control); push = next control; double-push =
  block on/off; long-push = model list with live preview (push keep, ◁ cancel); ◁/▷ = previous/next block;
  hold ◁/▷ = move block left/right; ◁+▷ = home.
- open questions to the user: save behaviour (`*` + prompt only when leaving an edited preset, vs a quicker
  prompt on going home); whether holds on ◁/▷ are free (tuner?).
- Art budget: ~9 blocks x ~35 models, small + large pictures ≈ 60–90 KB of the ~160 KB free.

## NAM (clone) captures in the UI (decided with the user)
- Amp slot mode "Clone" is renamed "NAM". Home screen: the AMP square shows a NAM picture and the label "NAM".
- Amp+cab capture selected: the IR block is switched off automatically and its square shows that the cab is
  inside the capture (IR picture greyed, small "in NAM" tag / link mark between the AMP and IR squares).
  If the user tries to switch the IR on: a short message "This NAM already includes a cab. Adding an IR doubles
  it." with "Keep off" (default) / "Use anyway" - the user decides, nothing is blocked silently.
- Amp-only capture selected: IR switched on (preset's IR, else 4x12 V30); a 1 s hint "Amp-only NAM: IR on".
- Edit page for a NAM: model name = slot name, a small "AMP+CAB" or "AMP ONLY" badge under it.
- Tone curve for NAM blocks: from the clone's two filters (small-signal), labelled "Tone".

## Settings pages (agreed with the user)
One list per page (turn = change the highlighted item at once, push = next item, ◁/▷ = page, ◁+▷ = home,
auto-save); control per type (list ◀ name ▶, level bar + value, on/off switch); bottom area = live preview:
Display: theme preview | I/O (Direct, USB REC, RE-AMP): routing diagram | USB (FX REC, BT REC, Monitor): live
meters | Level (Input Level): live input meter with clip mark | G-EQ (on, Model, Low Cut): EQ curve |
MIDI (Same AGN, MIDI CH, Tempo): last MIDI message / clock BPM | BT: status, device | Boot: what it does.
To find out in the firmware: what ECO, Same AGN and Boot do; whether live levels / MIDI reach the MCU.
Meanings (from the CFW 1.0 manual, re/cfw/cfw_manual.txt; pocketmaster-cfw.guitar-training-generator.com/manual):
- ECO ON: screen dims to minimum after ~5 s without input (stays bright in tuner, looper, drums playing).
- SAME AGN (MIDI): what a Program Change for the preset already playing does: OFF / CYCLE (steps scenes
  BASE -> SC1 -> SC2) / BACK (previous preset). MIDI page 2: MIDI MAP, DRM SYNC. TEMPO: PRESET or GLOBAL.
- I/O: Direct (hear the pedal at the outputs), USB REC (what goes to the computer), RE-AMP (effects process the
  computer's audio; OFF at every power-on).
- Settings tabs in CFW 1.0: Level, G-EQ, USB, Boot, Display, BT, MIDI, I/O, Reset, About. Boot: still to check.

## Phase 0 result: first test build (not flashed)
build/ui1 = dl14 + 86 bytes of our C code (ui/hello: GCC 13 for NDS32) at flash 0x168000 (CPU 0x178000); the stock
flush callback's call at 0x4A9CC now goes to our hook, which draws a 6x6 magenta square at the top right of every
frame and passes the pixels on to the CFW theme hook / LCD. Proves: compiler, placement, hooking, drawing.
Open risk: the CFW may store its extra IR/clone slots in the flash gap; stock code uses 0x180000+ only.
