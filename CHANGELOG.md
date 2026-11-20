# Pocket Master — Tone Upgrade: what's new

## What you'll hear

- **Drives and amps sound smoother and more like real gear.** The harsh, buzzy edge that digital pedals often add,
  especially on high-gain sounds and single notes high up the neck, is mostly gone. Chords stay clear even with lots of gain.
- **Cabinets sound bigger and fuller,** with a tighter, deeper low end, closer to a mic'd amp in a studio.
- **The Octave and Pitch effects are now in tune,** so octave sounds no longer clash with your playing.
- **New delays:** a clean digital delay, tape and analog-style delays whose echoes get warmer as they fade, a
  slapback and a warm echo, all with a little stereo spread.
- **NAM captures that sound like the capture (new clone engine).** Load a NAM capture into a clone slot and the
  pedal plays it with a multi-stage amp model plus the capture's own cab, instead of Sonicake's one-stage clone.
  You can swap the cab live with the clone's new **Cab** knob (factory cabs or your User IRs).
- **Fewer, better choices:** weak and duplicate effects were removed, so the menus are shorter. Your presets still
  work; nothing was deleted from your saved sounds.

## How to read the numbers

All numbers come from recordings made on the pedal itself, with the same test sounds for the original effect and
the new one.

- **Original** = the effect that came with the pedal (Sonicake's firmware plus the community CFW 1.0.2).
- **Harshness** = how loud the unwanted, buzzy "digital" sound is compared with the actual guitar sound.
  It is measured in dB: the more negative, the cleaner. Every 6 dB less is about half as loud; 20 dB less is
  a big, easily heard difference.
- **Tone match** = how close a new amp sounds to the original amp in the same slot (average difference across
  the frequency range). Under about 2 dB is a subtle difference; the character is the same.

Pedal builds: `build/dl14/PocketMaster_CFW1.0.2+dl14.bin` (release); `build/clone5/PocketMaster_CFW1.0.2+clone5.bin`
(release + new NAM clone engine, in test).

---

## At a glance

| Area | Before | After | What you hear |
|---|---|---|---|
| Drives | 8 originals, several harsh | 6 rebuilt + Bass Drive, 1 removed | Much smoother, real pedal voices |
| Amps | 38 originals | 16 carefully chosen, rebuilt | Same tone, far less harshness (~22 dB) |
| Cabinets | 16 short recordings | 16 professional cabinet recordings | Fuller, deeper, more realistic |
| Octave / Pitch | Out of tune | In tune | Octaves sit right with your playing |
| Delays | 24, all mono except Ping Pong | 5 new, 2 removed | Warmer, more musical repeats, slight stereo |
| NAM / Clone | Sonicake clone (1 stage) | own multi-stage engine + cab, Cab knob | Much closer to the capture; cab swappable |
| Reverbs | 15 | unchanged | — |
| Presets | — | none deleted; 19 factory presets updated | Old presets keep working |

---

## Drives

*What you hear: each drive now behaves like the real pedal it is named after — smoother distortion, no buzzy
edge on top, and the RAT and DS-1 stay musical with the gain all the way up.*


| New | Replaces (same menu slot) | Knobs | Harshness, new (gain 50) | Harshness, original |
|---|---|---|---|---|
| **TS808** (Tube Screamer) | Scream | Gain, Tone, VOL | −45 … −63 dB | ≈ −25 dB |
| **Klon** (Centaur) | Butter OD | Gain, Tone *(new knob)*, VOL | −60 … −69 dB | −15 … −33 dB |
| **DS-1** | JP Dist | Gain, Tone, VOL | −65 … −73 dB | ≈ −13 dB, falls apart at full gain (+45 dB) |
| **Fuzz Face** | Shark | Fuzz, Tone, VOL | −42 … −66 dB | ≈ −15 dB |
| **RAT** | Dark Mouse | Gain, Tone, VOL | −34 … −63 dB | −21 … −33 dB, breaks up at full gain (+3 dB) |
| **Big Muff** | Grey Fuzz | Sustain, Tone *(new knob)*, VOL | −52 … −68 dB (−18 dB at full gain, 4 kHz) | −16 … −32 dB |
| Bass Drive | — | unchanged | | |

- Each drive is a circuit model running 4× oversampled with anti-aliased clipping; on the pedal it matches its
  reference model closely (error 0.01–0.13).
- **Removed:** Red Fuzz (our Fuzz Face covers it). Its 3 presets (F03, F25, F26) now use Fuzz Face.
- Presets using Butter OD / Grey Fuzz keep Gain and VOL; the new Tone knob starts at the middle.
- Processing cost per drive: 20–28 % of the audio engine.

## Amps (16, from clean to high gain)

*What you hear: the amps keep the character of the originals, but sound smoother and more "amp in the room",
with much less harsh top end on high-gain sounds. The clean amps feel a bit more open and dynamic.*


Each amp is our own model (tube-style preamp stages, real tone-stack circuit, power stage, presence/resonance),
tuned to sound like the recorded original amp, but processed so it stays smooth. Same knobs as the original amp in that slot.

| New amp | Menu slot | Tone match | Harshness, new | Harshness, original |
|---|---|---|---|---|
| Tweed Deluxe | TWD Deluxe | 2.1 dB | −55 dB | −45 dB |
| Twin Reverb | Dark Twin | 1.8 dB | −61 dB | −39 dB |
| Bassman | B-Man B | 1.6 dB | −57 dB | −33 dB |
| AC30 Normal | Voks 30N | 1.8 dB | −55 dB | −30 dB |
| AC30 Top Boost | Voks 30TB | 2.1 dB | −38 dB | −21 dB |
| JC-120 | Jazz 120 | 0.9 dB | −74 dB | −70 dB |
| JTM45 | Brit 45 | 3.6 dB | −55 dB | −47 dB |
| Plexi | Brit 50 | 0.9 dB | −49 dB | −28 dB |
| JCM800 | Brit 800 | 1.4 dB | −46 dB | −22 dB |
| Mark IIC+ | Calif IIC+ | 1.8 dB | −39 dB | −20 dB |
| SLO-100 | Sol 100 LD | 1.7 dB | −37 dB | −14 dB |
| Friedman | Flyman B1+ | 1.7 dB | −45 dB | −22 dB |
| Dual Rectifier | Calif DualM | 2.2 dB | −37 dB | −22 dB |
| 5150 | Halen 51 | 1.1 dB | −41 dB | −20 dB |
| VH4 | Dizzy VH+ | 2.0 dB | −44 dB | −26 dB |
| SVT (bass) | A BassVT | 2.0 dB | −67 dB | −70 dB |

- Overall (64 recordings): tone match **1.7 dB**, harshness **−47 dB vs −25 dB** (about 22 dB cleaner).
- Known difference: the clean/edge amps (Twin, Deluxe, AC30N, Bassman) compress less when played softly than the originals
  (feel more open and dynamic); JTM45 is the loosest match.
- Processing cost: 63–78 k engine units per amp (RAT + amp + cab ≈ 80 % of the engine, no overload).
- **Removed from the menu (22):** B-Man N, Brit 50JP, Brit 900, Bog XT, Bog XT M, Bog SV CL, Sol 100 OD, Dizzy VH,
  Eng 120, Eng Power, Calif DualV, Calif IV LD, Calif Star CL, Calif Bass, Voks Bass, Superb CL, Superb OD,
  Supero 2 OD, Doctor CL, Doctor OD, Flyman B1, Tanger R100.
- Presets re-pointed: F01 Bog XT → Friedman, F10/F24 Sol 100 OD → SLO-100, F17 Eng Power → 5150,
  F19 Dizzy VH → VH4, F46/F50 B-Man N → Bassman (knob values carried over by name).
- Fix found on the way: the 5150's Presence knob is its 7th parameter (was read from the wrong position).

## Cabinets (16 factory cabinets replaced; your User IR slots untouched)

*What you hear: a bigger, fuller cabinet sound with a deeper low end — the original high-gain 4x12s were especially thin.
The "B" and "C" versions of a cabinet are the same cabinet recorded with a different microphone.*


Close-miked IRs from TONE3000, shortened to the pedal's 512 taps with a fitted minimum-phase method
(tone error vs the full-length IR 0.1–0.6 dB; plain cut 0.3–1.3 dB). Verified on the pedal (spectra match 1.00).

| Cab | IR source (speaker, mic) |
|---|---|
| Deluxe 1x12, Deluxe 1x12 B | 1966 Deluxe Reverb, Jensen P12Q — SM7B cone / i5 cap |
| Twin 2x12, Twin 2x12 B | 1971 Twin Reverb, Oxford 12T6 — SM57 / R121 cap edge |
| Bassman 4x10 | Jensen P10R — SM57 |
| Vox 2x12, Vox 2x12 B | AC30 Alnico Blue — SM57+R121 blend / e906 dustcap |
| JC 2x12 | Roland JC-120 — SM57+MD421 blend |
| 4x12 Green, 4x12 Green B | Marshall 1960TV G12M — SM57 / U87 |
| 4x12 T75, 4x12 T75 B | Marshall 1960 G12T-75 — SM57 / SM58 |
| 4x12 V30, V30 B, V30 C | Mesa 4FB / Orange 4x12 V30 — SM57 / 421+M160 / SM57 1" |
| SVT 8x10 | Ampeg 8x10 — SM57 |

- The original cabinet recordings were short (9 ms; only 3 ms on the high-gain 4x12s), which made the low end thin.
- Mic choice = the plain / "B" / "C" entries of the same cab.
- Not done: Low cut / High cut knobs (worked in simulation, not on the pedal).

## FX2

*What you hear: octave-down and octave-up voices are in tune with your guitar, with less warble.*


| Effect | Original | New |
|---|---|---|
| **Octave** | voices +37 / −19 cents out of tune, junk −24 dB | in tune (0 / +2 cents), junk −31 dB |
| **Pitch** | +37 / −19 cents, junk −32 dB | in tune (0 / +1 cents), junk −34 dB |

Rebuilt as a SOLA pitch shifter (correlation-matched splices); passes the load test together with
RAT + amp + cab.

## Delays

*What you hear: the new delays have smoother, more musical repeats. EP-3 and DM-2 echoes get darker and warmer as
they fade, like real tape and analog units; Digital stays crystal clear.*


| New | Menu slot (was) | Character | Measured on the pedal |
|---|---|---|---|
| **Digital** | Shiny | clean, full range, slight stereo spread | repeat harshness −35 dB (Pure −23), wobble 0.8 c (Pure 4.9) |
| **Slapback** | Flash | short, slightly warm | harshness −50 dB |
| **EP-3** | Float | Echoplex tape: preamp, wow/flutter, darkening repeats | wobble 13 c, −2.6 dB treble per repeat |
| **DM-2** | Damage | bucket-brigade analog: dark, soft, slow movement | −2.8 dB treble per repeat, harshness −33 dB |
| **Echo+** | Glost | warm classic echo | harshness −33 dB |

- All with correct tap/sync note values; cost 5–7 % of the DSP each.
- **Removed:** Mag, Sweep (presets F04, F10, F21, F33, F43 re-pointed to EP-3 / Digital).
- Kept: Pure, Slap, Warm, Tube, Reverse, Analog, Ping Pong, Studio Delay, Tape Echo, Dual Delay, Shimmer Delay,
  Swell Delay, Lo-Fi Delay, Echo, Dark, Shake, Flutter.

## NAM captures (Clone slots) — in test

- **Converter** (`tools/nam2amp.py`, on the computer): a `.nam` file becomes our amp model, trained on real guitar
  playing from many styles. It detects amp-only vs amp + cab captures from the sound (file labels are often wrong)
  and, for amp + cab captures, splits out the cab.
- **Engine** (new clone block on the pedal): our multi-stage amp (the same code as the 16 amps) followed by the
  pedal's own cab stage, about 45 % of the sound processor. Sonicake-made clones are no longer played (they pass the
  dry sound).
- **Cab knob** (6th clone knob): 0 = the capture's own cab, 1–15 factory cabs, 16–25 User IR 1–10, switchable live.
  Keep the IR block itself off in NAM presets (with the new engine it would mute the sound).
- **Results** (error against the real capture, 0 = identical; held-out playing from 4 songs):

| Capture | Sonicake's conversion | New engine |
|---|---|---|
| MES Recto + 808 + cab (on the pedal) | 0.54 | 0.10 |
| Fender Super Reverb + cab (on the pedal) | 0.10 | 0.01 |
| JCM800 2203, amp only (on the pedal) | 0.21 | 0.07 |
| 11 captures, median (computer) | 0.38 | about 0.10 |

  Better than Sonicake on 9 of 11 captures; two vintage amp-only captures (Bassman, JTM45) still convert poorly.
- Limits: the clone code cuts the sound above ~10–12 kHz (some top-end "air" is lost); converting takes 15–25 min
  per capture on a Mac for now.

## Not changed (measured, kept as they are)

- **Reverbs:** all 15 originals. Their tails have normal lengths (Hall 1.6–3.1 s, Church 2.6–4.4 s, Plate 1 2.9–4.4 s);
  the measurable weakness is a metallic colouration (~22 dB peaks). A rebuilt reverb engine cost 74–80 % of the
  DSP on this hardware, so a version that fits would not be clearly better.
- FX1 (all 27), the noise gate, EQ, Bass Drive, the remaining FX2 effects.

## Presets

No preset was deleted. 19 factory presets were updated automatically so nothing points at a removed effect
(drives: F03, F25, F26 and knob layout F02, F15, F16, F17, F19, F30, F33, F38; amps: F01, F10, F17, F19, F24, F46,
F50; delays: F04, F10, F21, F33, F43). A preset that still asks for a removed effect simply bypasses that block.

## Known limits / to do

- Looper not yet tested together with the new delays (uses the same external memory chip).
- Cab Low/High cut knobs; wider stereo option for the new delays.
- NAM: Bassman / JTM45-style captures; one-command converter; screen support (see UI).
- UI work (home/edit/settings screens, gear art, load bars, NAM cab block) — designed, groundwork done.
- Full on-pedal test of every new effect with real guitar DIs — after the UI work.
