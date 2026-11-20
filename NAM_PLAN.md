# NAM capture plan (clone slots)

Goal (decided with the user): NAM captures stay user-loadable into the 5 clone slots (Sonicake Manager or our
script). We do not add them as amps. Deliverable: a terminal script `.nam` -> `.clo` that sounds closer to the
capture than Sonicake Manager's conversion and fits the stock clone engine (no new clone engine).

## Pedal behaviour to add (screen-controller firmware; flash only with the user present)
- Rename the amp slot's mode "Clone" to "NAM" ("Basic" stays).
- Capture type: the script stores amp-only vs amp+cab in the clone file. Type comes from the NAM file's
  `gear_type` tag (amp, pedal, pedal_amp, preamp -> amp-only; amp_cab, amp_pedal_cab -> full rig). Untagged
  files: high-band test (energy 6-12 kHz vs 0.5-3 kHz; full rigs measured -31..-36 dB, amp-only -13..+7 dB;
  threshold -22 dB).
- When a NAM slot is picked: amp+cab capture -> IR block off; amp-only -> IR block on, using the IR the preset
  already has, else 4x12 V30 (user choice "a"). The user can still change the IR afterwards. Clones made by
  Sonicake Manager carry no type -> unchanged behaviour.

## Known so far
- Clone mode in a preset = AMP enable bit + clone enable bit, clone slot in the clone fx id. The IR block works
  after a clone.
- Sonicake's sample conversion `cloFile.clo` was made from `~/Downloads/MES DRECF RD Gain2 BAL O808 CAB.nam`
  (user; confirmed offline: its filters' tone is 1.4 dB from that capture vs 3.2-15.7 dB for 8 others).
- `tools/clone_sim.py` runs the stock clone code offline; the first 128-tap filter checks out, the 512-tap second
  filter does not yet (one engine instruction still unknown).

## Test plan (needs the 3.5 mm jack; the user says when it is free)
1. Clone engine identification (~30-45 min): simple test clones in slot 5 (delays, single taps, level steps,
   one parameter at a time), recorded through the pedal, to pin down the second filter and the nonlinearity.
   Fix `clone_sim.py` until it matches the pedal.
2. Baseline: Sonicake's MES clone (`cloFile.clo`) on the pedal with the guitar DI; score against the real MES
   capture: tone difference, ESR, gain curve.
3. Ours: convert the same MES capture with our script; same scoring; A/B clips for the user in `audio/listen/`.
4. Repeat 2-3 on an amp-only capture (5150): user imports it in Sonicake Manager and exports the clone.
5. Claim "better" only if the numbers show it on both captures.
6. Then the firmware part above (rename + auto IR), with the user at the pedal.
- Slot 5 is the user-approved test slot; leave it empty at the end (best: delete in Sonicake Manager).

## Decision 2026-11-20 evening: own clone engine (user: "better returns here")
Listening (user): our stock-format clones (v2/v3) sound more driven / harder clipping, less smooth top than the
NAM (all 4 test captures), JCM800 quieter; Sonicake smoother but further off. Numbers (ESR, mean band tone) did
not show it -> add "fizz" (high-overtone excess on loud passages, pre-emphasis) and "drive" (compression vs input
level) measures. Limit: one saturator stage in the stock clone format.
Plan (T3, user approved the direction; flash only after asking):
1. Converter nam2pedal v2: our multi-stage amp model (amp_core, 2-3 stages, os 2x) + 512-tap cab FIR for full rigs;
   trained on guitar_di train takes; level-matched; scored on held-out R takes incl. fizz/drive; exact engine sim.
2. Clone file variant ("PMAM" magic inside the VTSI container, CRC valid): amp params (36 f32) + flags (type,
   version) + FIR 512 (identity for amp-only). Fits the 2560-byte device data area.
3. Firmware: new CLONE module = dispatcher. Stock clone data -> stock clone code unchanged; ours -> amp_core
   engine program + FIR program (~75k + ~64k engine units).
4. Pedal tests: A/B + clips, stock clones unchanged, switching/crash, load. Check Sonicake Manager Import Clone.
- 2026-11-21: user listening: MES + Super Reverb on the own engine 'sound perfect' -> NAM method green. UI hook test: square stays magenta under themes (our hook after the theme step works).
