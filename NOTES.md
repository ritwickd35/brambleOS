# Sonicake Pocket Master firmware V1.3.3: reverse-engineering notes

Status: first pass. Each point is tagged **[confirmed]** (checked against the bytes or code) or **[inferred]** (a good guess that still needs proving).

## 1. Hardware picture

There are two processors. Each one has its own code in the update file.

| Part | Evidence | Role |
|---|---|---|
| **MCU: MVSilicon BP10 series**, Andes NDS32 V3 core with FPU | Banner `MVsilicon B1 SDK`, `Mountain View Silicon Technology`, chip tag `*BP10-LYM`. Disassembles cleanly as NDS32 (`j`/`jal` vector table at 0, `$gp=0x2000fa40`) **[confirmed]** | UI and screen, encoders and keys, Bluetooth audio and BLE (SoundLink app), BT MIDI, USB audio and USB MIDI, presets, looper, drum/metronome, power. Runs in place from flash at address `0x00000000`; RAM is at `0x20000000` **[confirmed]** |
| **DSP: an ARM Cortex-M with single-precision FPU** (M4F/M7/M33 class; the exact chip is still unknown) | Thumb-2 + VFP code, CMSIS `SystemInit` (sets VTOR/AIRCR), ARM-compiler C library (`__main`, `SIGRTMEM`), vector table at image offset 0x400 **[confirmed]** | The audio signal chain: NR, FX1, DRV, AMP or NAM clone, CAB IR, EQ, FX2, DLY, RVB. The MCU logs its version as `dspVer` |

The MCU and DSP talk over SPI. The MCU has a "SPIS Audio task" (SPI slave) **[inferred]**. Opening the case and reading the chip markings would settle the DSP part number. That matters, because it decides the compiler flags and the memory map.

## 2. Update file container ("HTFW")  **[confirmed: `pmfw.py pack` rebuilds the original byte-for-byte]**

```
0x00 "HTFW"
0x04 u32 0x0001AC24   UNKNOWN. Not a CRC/sum/adler of anything tried. Model ID? Checksum? (see §6)
0x08 u32 total file size
0x0C "Pocket Master\0..." (16 bytes)
0x1C 'V',1,3,3        version
0x22 u16 section count (5)
0x24 u32 payload size
0x38 5 x 16-byte section entries:
     u16 BIG-endian CRC-16/MODBUS of the section data, u8 0, u8 type, u32 flash address, u32 offset(from 0x88), u32 size
0x88 payload
```

| # | Type | Flash addr | Size | Contents |
|---|---|---|---|---|
| 0 | 0x63 | 0x200000 | 50 KB | **DSP kernel**. Cortex-M image; the whole section is linked at **0x4000**. The first 0x400 bytes are a header (`V132` = DSP version), then vectors at 0x4400 (reset 0x4D90, SP 0x20006AE8) |
| 1 | 0x67 | 0x240000 | 292 KB | **DSP effect modules**: loadable code blobs, one per effect (see §3) |
| 2 | 0x66 | 0x280000 | 32 KB | **Cab catalog**: 16 factory cabs + User IR 1–5 (names, mic text, IR data; format not decoded yet) |
| 3 | 0x62 | 0x000000 | 1.36 MB | **MCU application** (NDS32): UI, BT, USB, MIDI, looper, images (GIF/PNG), fonts |
| 4 | 0x65 | 0x190000 | 244 KB | **Factory presets** (0x1000.., 1 KB each, magic `A5 5A`, name at +0x0A, float params) **and the effect database** (at +0x10000: UI names, params, min/max/step/default) |

The MCU bootloader (`bootVer`) is **not** in this file. An update therefore probably leaves the boot code alone, which helps with recovery. This is **[inferred]**: check it before flashing anything.

## 3. DSP effect modules (section 1): where new effects go

Both section 1 and the effect DB in section 4 use the same table layout: `u32 ?, u32 size, u32 data_start, u32 -1, u8 0xff, u16 0, u8 group_count(=11)`, then 11 offsets to `{u32 count, u32 offset[count]}` **[confirmed]**.

`python3 pmfw.py modules <fw>` prints the whole table. The `strings=` column is the screen title (if any) followed by the parameter names, as stored in the effect DB. Summary:

| Group | Count | RAM slot (code linked at) | Effects |
|---|---|---|---|
| 0 NR | 1 | 0x10000000 | Gate |
| 1 FX1 | 15 | 0x10001000 | COMP 1/2, ITouch Wah, Auto Wah, Boost, A/B-Chorus, Flanger, Phaser, Vibe, Vibrato, Tremolo, Sine/Bias Trem, **AC G** |
| 2 DRV | 8 | 0x10002800 | Scream, Butter OD, JP Dist, Shark, Dark Mouse, Grey/Red Fuzz, Bass Drive |
| 3 AMP | 22 | 0x10003800 | TWD Deluxe … Bog XT, A BassVT, Voks Bass |
| 4 CAB | 1 | ~0x10006400 | IR convolver (cab data from section 2) |
| 5 EQ | 3 | ~0x10007C00 | GT EQ 1/2, Bass EQ |
| 6 FX2 | 17 | 0x10009000 | FX1 set + Octave, Pitch, Detune |
| 7 DLY | 9 | 0x1000C000 | Pure, Slap, Warm, Mag, Tube, Reverse, Analog, Sweep, Ping Pong |
| 8 RVB | 10 | 0x10018400 | Air … Dream (tiny ~250 B blobs → shared reverb engine) |
| 9 CLONE | 1 | 0x10003800 (**shares the AMP slot**) | **NAM player**, 6.3 KB of code + 3.3 KB state |
| 10 shared | 2 | ~0x10018Dxx | shared code without a module header (likely the reverb engine and/or helpers) |

Module blob layout **[confirmed for the size fields, inferred for the entry roles]**:
```
u32 header_size (0x24/0x28) | u32 code_size | u32 total(=hdr+code) | u32 state_size | u32 entry0 (init?) | u32 entry1 (process?) | …
code[code_size]  -> copied to the group's RAM slot; absolute (movw/movt) refs to 0x1000xxxx; no calls outside the blob
```

The FX1 and FX2 copies of the same effect are the same source code, linked at different slots. So modules are **fixed-address overlays**: one per signal-chain position. There is no relocation step.

### What this means for adding DSP features
1. **Easiest: replace an existing module.** Compile your own effect in C for the same slot, keep the same entry-function ABI, and drop it in place of an effect with the same parameter count. Then rename it in the effect DB (section 4) and rebuild with `pmfw.py pack`. The MCU UI appears to be data-driven from the effect DB ("Get Audio Effect Name/Parameter From FLASH"), so the UI should pick up a new name and parameter ranges **[inferred]**.
2. **Next: append a module.** Bump the group count in **both** tables (section 1 and section 4) and add a DB record. It is not yet known whether the MCU or the DSP has hard-coded per-group limits. Check MIDI/CC tables and the preset format for limits too.
3. **Still to reverse:** the module ABI. Find the loader/dispatcher in the DSP kernel (section 0): what `entry0`/`entry1` receive (buffer pointers, frame size, parameter array), the sample format (float32?), the block size, the sample rate (48 kHz?), and how parameters arrive from the MCU. The quickest route: load section 0 at 0x4000 in Ghidra and follow references to the 0x10000000 slots.
4. Toolchain once the ABI is known: `arm-none-eabi-gcc -mthumb -mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -mfloat-abi=hard -O2 -ffreestanding -nostdlib`, linker script `. = <slot base>`, entry functions first, then `objcopy -O binary` and prepend the 0x24-byte header. Adjust `-mcpu` once the DSP chip is identified.

## 4. MCU application (section 3): UI and new non-DSP features

- Mostly MVSilicon "B1 SDK" plus FreeRTOS-style tasks ("Flash Task", "SPIS Audio task", "DRUM Audio task"), BT stack (A2DP/AVRCP/HFP/BLE GATT), USB device (audio + MIDI), FatFs.
- Strings to anchor on: `Anti-Touch Protection`, `Factory reset…`, `METRO 1/4…`, `Recording/Playing/Overdub` (looper), `Pocket Master MIDI`, `Get Audio Effect Name From FLASH!!!!!!`, `Load BP From Flash Fail`, `Remain mem size: %dK`.
- Strings are referenced as `sethi rX, #hi20 ; ori/addi rX, rX, #lo12` with absolute addresses (base 0). For example, `sethi $r1, #0x130` (strings at 0x130xxx) appears at 0xFCD6, 0x1437A and other places.
- Full disassembly: `re/mcu_app.nds32.dis` (GNU objdump, `-m n1h_v3 -EB`).
- Adding MCU code: the image has trailing free space up to 0x190000 (the app ends at 0x15BB60, so about 210 KB is free). New code can be placed there, built with an NDS32 GCC (`nds32le-elf-gcc`, e.g. Andes' or the old GCC ≤13 toolchains), and reached by patching a `jal` (a ±16 MB PC-relative call). Check first that nothing else uses 0x15BB60–0x190000 at runtime (e.g. BT pairing records, `FlashBtAddress`, "erase last bt addr area"). **[inferred]**

## 5. Tools

```bash
python3 re/pmfw.py info    "Pocket Master Firmware V1.3.3.bin"
python3 re/pmfw.py unpack  "Pocket Master Firmware V1.3.3.bin" re/unpacked
python3 re/pmfw.py pack    re/unpacked re/modded.bin        # recomputes section CRCs
python3 re/pmfw.py modules "Pocket Master Firmware V1.3.3.bin"
python3 re/pmfw.py presets "Pocket Master Firmware V1.3.3.bin"

# NDS32 disassembler (binutils 2.42 built for nds32le-elf) in Docker:
docker build -t pmre -f re/tools/Dockerfile.nds32 re/tools
docker run --rm -v "$PWD/re/unpacked":/w -w /w pmre nds32le-elf-objdump -b binary -m n1h_v3 -EB -D 3_mcu_app_00000000.bin
```

Ghidra: the ARM parts load well (`ARM:LE:32:Cortex`). Load section 0 as a raw binary at base **0x4000**, so file offset 0x400 = vector table at 0x4400 and reset = 0x4D90. Each module blob: skip its header and load at the slot base. Stock Ghidra has **no NDS32 support**; use objdump or IDA, or try a community NDS32 SLEIGH module.

## 6. Open questions / next steps (in order)

1. **Header word @0x04 (0x1AC24).** Get one older firmware (V1.2.2 or V1.1.0) from Sonicake. If the word changes in a non-obvious way, it is a checksum and must be cracked before any modded image will flash. If it stays the same, it is a model ID.
2. **Update path and recovery.** Find out how Sonicake Manager pushes the file: capture the USB traffic (Wireshark + USBPcap on Windows) during an official update. Is it HID? Vendor-class? Does it go per section? Who checks the CRC? Is there a boot/recovery mode (a button held at power-on)? **Do not flash a modified image until you know how to recover.**
3. **First safe test:** change only a factory-preset name in section 4, repack, flash. That proves the whole chain without touching code.
4. **Identify the DSP chip** (open the case).
5. **DSP module ABI** (§3.3). Then build a trivial "pass-through + gain" module and swap it in place of, e.g., `Red Fuzz` (DRV #6, one of the simplest modules: 0x148 bytes of code).
6. Decode the cab IR format (section 2) and the NAM ("Clone") model format/limits used by the CLONE module.

## 7. Round 2 findings

- **Language: English is already built in.** The MCU holds two parallel UI string tables: Chinese (UTF-8) at ~0xD12C0 (`中文`, `效果`, `鼓机`…) and English at ~0xD15A0 (`English`, `Effects`, `Settings`, `Drum`…). The language menu offers `English`/`中文`. More languages would need a third table, plus font glyphs for any accented letters, plus the menu entry. **[confirmed strings; table and pointer layout not yet decoded]**
- **USB device = Audio + MIDI only, no HID or vendor interface.** The configuration descriptor at 0x1336D4 has Audio Control, 2× Audio Streaming (**44.1 kHz, 16-bit, stereo**) and **MIDI Streaming** ("Pocket Master MIDI"). The descriptor's VID/PID fields are 0 (filled in at runtime). Build stamp: `8.7.1 build @ Apr 29 2025 16:04:02`. **[confirmed]**
- **Editor protocol is very likely MIDI SysEx.** The MCU function at 0x3D304 accepts `F0 … F7` messages ≥ 6 bytes and matches a 4-byte header held in RAM (gp-11144), then dispatches. This means Sonicake Manager / SONICLINK most likely talk SysEx over USB-MIDI and BLE-MIDI. **[inferred]**
- **Flash-address puzzle.** Section 1 (0x240000, 0x49050 bytes) would run to 0x289050, past the start of section 2 (0x280000). So the "flash address" field can't be a plain address in one flash for both. Possibilities: separate devices/regions, or a region ID. Must be resolved before resizing sections. **[confirmed overlap; meaning unknown]**
- **DSP RAM per signal-chain slot** (from module link addresses) **[inferred]**:

  | Slot | Range | Size |
  |---|---|---|
  | NR | 0x10000000–0x10000FFF | 4 KB |
  | FX1 | 0x10001000–0x100027FF | 6 KB |
  | DRV | 0x10002800–0x100037FF | 4 KB |
  | AMP / CLONE | 0x10003800–0x100063FF | 11 KB |
  | CAB | 0x10006400–0x10007BFF | 6 KB |
  | EQ | 0x10007C00–0x10008FFF | 5 KB |
  | FX2 | 0x10009000–0x1000BFFF | 12 KB |
  | DLY | 0x1000C000–0x100183FF | 49 KB |
  | RVB + shared | 0x10018400– | ~7 KB |

  The kernel stack/data is at 0x20000000–0x20006AE8. Delay goes up to 1000 ms, which doesn't fit the 49 KB slot, so delay/looper buffers live elsewhere. The MCU factory test prints `SDRAM SUCCESS`, so there is probably external RAM somewhere.
- **Hidden factory test mode** in the MCU: `Please Test BT/Audio/Enc Key`, `Screen Light`, `SDRAM SUCCESS`, and prints `dspVer/mcuVer/bootVer/HwVer`. How to enter it is not yet found.
- The DSP kernel references the Cortex-M **DWT cycle counter** (0xE0001000). It may already measure CPU load; a lead for measuring headroom.
- A 148×48 animated GIF sits at 0x1054BC (probably the boot animation) behind a small resource header (`03 50 02 06 …`, size 0x1AC93). This suggests a resource table for UI images.

## 8. Sonicake Manager 1.5.2 (macOS): what the desktop app reveals

The app is a Flutter UI plus a native C++/JUCE library: `Contents/Frameworks/5868USB.dylib` (arm64 + x86_64, with readable exported function names). "HT" prefixes (`HTMIDIManager`, `HTDevice`, `HTFirmware`, `HTKPA`) match the `HTFW` container magic. **[confirmed]**

- **Transport is CoreMIDI** (JUCE `MidiOutput`, `HTMIDIManager`, `sendMidiMessage`). MIDI Monitor's spy can see the traffic. **[confirmed]**
- **"NAM conversion" is a re-capture, not a file-format conversion.** Exports include `namConvertClo`, `namConvertCloData[WithProcess]`, `cloConvertSampleRate`, `convertNamToNamb[WithSlim]`. The strings say: `HTKPA startClone failed. inputSignalPath=`, `NAM process failed at frame`, `NAM to CLO conversion did not produce a complete CLO buffer`. The library bundles NAM core (WaveNet, LSTM, ConvNet, `SlimmableWavenet`, `ContainerModel`, `A2FastModel`) and the r8brain resampler. The test signal `flutter_assets/assets/wavs/nam_input_wav.wav` is 70 s, 44.1 kHz, 16-bit stereo. So the app runs the .nam model over the test signal on the Mac, then fits Sonicake's own "clone" model (HTKPA) to the result, producing a **.clo** file. The pedal runs that clone model (DSP CLONE module), **not NAM**. **[inferred from names/strings; confirm by disassembly]**
- **Firmware update** goes through `HTDevice::startUpdateFirmware`, `deviceStartUpdate`, `checkCrc`, `isRealFirmware[WithDeviceName]`. `isRealFirmware` is the likely place to learn what the unknown header word @0x04 is.
- **Effect databases** in `flutter_assets/assets/data/{qap50,qme10,qme20,qam20,qbs60}_module_data.json`, one per device model. Each effect has an `fxid` (e.g. NR Gate `0x1b`, DRV `0x03000000`, AMP `0x07000001`, IR `0x0a000001`, DLY `0x0b000000`, RVB `0x0c00000b`, Clone `0x0f000000`), the real-world model it imitates (`origin`, e.g. Scream = Ibanez TS808), EN/CN descriptions, per-parameter `algId`, range/step/default, and display format code (`ValToStr_xxx`). The firmware effect DB records start with the same `fxid` (e.g. `1b 00 00 00` before NR). qap50/qme10/qme20 match the Pocket Master's module set; which one is the Pocket Master is not confirmed.

## 9. DSP compute and memory budget (static measurement)

**DSP kernel memory map.** This comes from the ARM scatter-load table at 0xE380 and the decompressed RW data at 0x2000218C.
- RAM code at 0x20000000 (0x218C bytes, copied from image 0xE3D0).
- RW data at 0x2000218C (0x230 bytes, compressed at 0x1055C).
- Zero-init: 0x1001F400 (3 KB), 0x200023BC (18 KB), and **0x29000000 (0xD7580 = 861 KB)**. That last one is a large buffer region, probably external RAM, likely used for delay/reverb/IR buffers.
- Internal RAM 0x10000000–0x1001FFFF = **128 KB**, fully carved into module slots.

**Official slot table** (RW 0x200021A4, 20 descriptors `{ram_base, ram_size, state_base, state_size}`) **[confirmed]**:

| Slot | Code RAM | State RAM (0x28xxxxxx) |
|---|---|---|
| NR | 0x10000000 + 4 KB | – |
| FX1 | 0x10001000 + 6 KB | – |
| DRV | 0x10002800 + 4 KB | 0x28004000 + 5 KB |
| AMP | 0x10003800 + 11 KB | 0x28005400 + 6 KB |
| CAB | 0x10006400 + 6 KB | 0x28006C00 + 3 KB |
| EQ | 0x10007C00 + 5 KB | 0x28007800 + 2 KB |
| FX2 | 0x10009000 + 12 KB | – |
| DLY | 0x1000C000 + 49 KB | – |
| RVB | 0x10018400 + 1 KB, shared engine 0x10018800 + 27 KB | – |
| **CLONE** | **0x10003800 + 17 KB** (takes over the AMP **and** CAB code areas) | 0x28005400 + 9 KB |

**Clocks.** RW 0x20002358 holds `192 000 000, 192 000 000, 96 000 000, 64 000 000`. Most likely the core clock is **192 MHz**, with 96 MHz and 64 MHz bus clocks. **[inferred]**
- Init enables the FPU (CPACR |= 0xF00000) and sets CCR.DIV_0_TRP. It never touches cache-enable bits or cache-maintenance registers, so the core is most likely **Cortex-M4F class (no cache)**, not an M7.
- At 44.1 kHz that gives **~4,354 CPU cycles per sample for the whole signal chain**: all blocks plus kernel and I/O.

**Built-in profiler.** RAM functions at 0x20001F90 / 0x20001FA8 read DWT->CYCCNT (0xE0001004). They record {last start, period, max period, busy, max busy}, i.e. a CPU-load meter. No callers were found (possibly unused in release builds). With an SWD probe, DWT can be read directly.

**Real NAM A2 on this DSP** (layer shapes from NeuralAmpModelerCore `NAM/wavenet/a2_fast.h`: 23 layers, K=6×21 + 15×2, dilations up to 239, head K=16):

| Model | MACs/sample | Weights | History (receptive field 6,331 samples ≈ 144 ms) | Est. CPU on 192 MHz M4F |
|---|---|---|---|---|
| A2-Lite (3 ch) | 1,731 | 7.3 KB | 74 KB float / 37 KB int16 | float ≈ 87–127 % of the whole DSP; int16 (SMLAD) ≈ 38 % |
| A2-Full (8 ch) | 11,776 | 47 KB | 198 KB float / 99 KB int16 | ≈ 220–830 %, **not possible** |

Conclusion: A2-Full cannot run on this chip. A2-Lite only fits as a hand-optimised **16-bit fixed-point** engine, with buffers in the 0x29000000 region. It would use roughly 40 % of the DSP, so the rest of the chain would have to fit in about 60 %. That is very likely why Sonicake re-captures NAM files into its own lighter clone model. The cycle-per-MAC figures are estimates and need on-device measurement (see the plan in the chat).

**Cross-check with a real A2 file.** `MES DRECF RD Gain2 BAL O808 CAB.nam` (TONE3000, 48 kHz) is a `SlimmableContainer` holding two WaveNets: **3-channel = 1,871 weights** and **8-channel = 12,146 weights**. Both exactly match the counts computed above, so the MAC and memory estimates use the right layer shapes. **[confirmed]**

**HTCache.** Sonicake Manager is sandboxed (`com.sonicake.sonicakemanager`). Its cache lives under `~/Library/Containers/com.sonicake.sonicakemanager/Data/…`, which macOS privacy protection blocks for other apps ("Operation not permitted").

## 10. USB protocol decoded

See **PROTOCOL.md**: nibble-encoded SysEx with CRC-8 framing; commands for presets, IR, clone and firmware; the preset TLV layout; the `.clo` format. The firmware update sends raw sections, byte-identical to the `.bin`, with no checksum or signature on the wire. The preset model tag `"\x0aEMQ"` suggests the Pocket Master's internal code is **QME-10**, so `qme10_module_data.json` in the app is likely its effect list. **[inferred]**

## 11. Language selection, and a correction to the MCU address map

**Correction.** The MCU app (section 3, flash 0x000000) runs at **CPU address 0x10000**.
- Evidence: startup sets `IVB = 0x10000`; 800 vs 38 printable string hits for base 0x10000 vs base 0; the .data copy source is 0x16AEC0 = file 0x15AEC0.
- So CPU address = file offset + 0x10000, and section 4 (flash 0x190000) appears at CPU 0x1A0000.
- `re/mcu_app.nds32.dis` has been regenerated with the right base. Addresses quoted earlier in §4/§7 (e.g. SysEx parser 0x3D304) are **file offsets**; add 0x10000.
- CPU 0x0000–0xFFFF is presumably a separate **bootloader** that updates don't overwrite **[inferred]**. Good news for recovery.

**Language.** **[confirmed in code]**
- .data image: file 0x15AEC0 → RAM 0x20003900, 0xCA0 bytes.
- `lang_tables[2]` at RAM 0x20003900: `[0]` = English table (RAM 0x20003C30), `[1]` = Chinese table (RAM 0x20003B08). Each holds 70 string pointers; index 4 is the language's own name, then NR, FX1, … "Disconnect".
- `get_text(i)` @0x15A9C = `lang_tables[lang][i]`; `set_lang(x)` @0x15AC4 (x < 2). The current language byte is at gp-45740.
- At boot, `@0x4E58C` sets **lang = (cfg->field_0x15C < 3) ? Chinese : English**.
  - `cfg` = pointer at gp-48024, initial value **0x1E0000** (CPU), i.e. flash 0x1D0000.
  - That is a factory configuration block (u16 magic 0x5AFF at +0, string at +0x42). It is **not part of the firmware update file**. Erased (0xFFFFFFFF = -1) also counts as < 3, so it means Chinese.
  - The same test is wrapped in `@0x4DAC0` (`is_cn_variant()`).
- Other `set_lang` callers only re-apply the current value: refresh @0x233E8, factory-reset restore @0x505A4/0x5061C, and @0x22E80 (forces English for one screen, probably factory test).
- **There is no menu option.** The language is fixed by the factory config value.
- Smallest patch to force English: file 0x3E598 `5C 10 00 01` (`slti $r1,$r0,#1`) → `84 20 92 00` (`movi55 $r1,#0 ; nop16`). Possibly do the same at file 0x3DACE for `is_cn_variant`. Untested; flashing needs the recovery plan first.

## 12. Board photo (component side, first look)

| Part | Marking (as readable) | What it is / role **[inferred unless stated]** |
|---|---|---|
| Large TSOP-54 | **Winbond W9864G6KH-6** (readable) | 64 Mbit = **8 MB SDRAM**, 16-bit, 166 MHz. Likely the DSP's external RAM (0x28/0x29xxxxxx regions) and/or looper/delay memory |
| QFN next to the SDRAM, own crystal X2 (U15) | "2531-BB / S2S25-000"? (not readable) | Probably the **DSP** (SDRAM controller + nearby 5-pin header J5). Needs a sharp close-up |
| Chip near the PCB trace antenna + 24.000 MHz crystal (bottom middle) | not readable | Probably the **MVSilicon BP10** (Bluetooth + controller). BP10 parts have a built-in audio ADC/DAC, which may be the actual converters |
| SOIC-8 U18 | SGM 8270-2? | Dual op-amp (analog input/output buffers) |
| SOIC-8 top middle | not readable | Op-amp or **SPI flash**: needs a close-up |
| U9 | TP4056 | Li-ion battery charger |
| J5 (5 holes, left of centre) and a 4-hole row below the SDRAM | – | Candidate **debug headers** (SWD and/or UART) |
| J4 + flex "B50-FPC-00" | – | Ribbon to the display/controls on the other half |
| Taped/foam rectangle near the USB-C ports | – | Unknown: shield, display back, or a chip under a pad |

Update from the second and third photos:
- The bottom-middle chip is a 4-sided QFP (~48 pins) next to a **24.000 MHz** crystal and the PCB meander antenna (bottom left). Very likely the **MVSilicon BP10** (Bluetooth + UI/USB controller).
- U15 (QFN-64-ish, "2531-BB / S2525-000"?, own crystal X2, series-resistor arrays toward the SDRAM) is very likely the **DSP**. The marking isn't a standard part number (custom or remarked).
- U17 and U18 carry the same SGM marking → both are op-amps.
- **No separate SPI flash chip on this side.** Flash is probably inside the chips, or on the other side. That means a clip-on CH341A backup may not be possible, and the backup plan has to change.
- J5 (5 pins, next to the DSP) and a 4-pin row (between the SDRAM and the BP10) are the debug/UART candidates.
- U15 marking (user-read): **"2531-BB / S2S2S-000"**.
  - "2531" is almost certainly a date code (2025, week 31); the SDRAM's own date code is "2522".
  - "S2S2S-000" is not a public part number; no web hits.
  - So the DSP is a custom-marked/private part. Identify it over SWD instead: CPUID @0xE000ED00 gives the core, and the CoreSight ROM table PID registers give the JEP106 vendor code.

## 13. How the controller enters update mode (CPU addresses)

**SysEx dispatcher @0x4CD28 (handlers the app implements).**
- **Write `11 xx`**: 11, 13, 1F, 21, 22, 23, 25, 26, 27, 31, 3F, 42, 43, 44, 46, 47, 48, 49, 4A, 4B, 4C, 4F, 6F.
- **Read `12 xx`**: 10, 20, 24, 30, 40, 41, 43, 45, 4F.
- The firmware-transfer commands (11 60/61/69/6E) are **not** in the app. They are handled by the bootloader.

**`11 6F` handler @0x4D088.**
1. ACK.
2. GPIO port 1 bit 17 low (@0x52110).
3. 100 ms delay.
4. @0x50790: GPIO port 1 bits 17 and 24 low, audio off (@0x53838), 100 ms delay, then @0x51FE0.
5. @0x51FE0 sets bits 0x02 | 0x20 in register **0x4000100C**, quiesces peripherals, and **jumps to address 0 (bootloader)**.
- So update mode is a warm jump with a flag in a register. A full power loss probably clears it **[inferred]**.

**Automatic fallbacks in the app** **[inferred, strong]**. Both call @0x50790, i.e. jump into update mode:
- **Startup** @0x4FA60, called from init @0x4FF24: after talking to the DSP, if the value the DSP reported (gp-41588, written by the DSP-message handler @0x4FDE0) is 0 → update mode. A DSP that doesn't answer properly therefore leaves the pedal in update mode, so DSP-side mods should be recoverable.
- **Counter** @0x4FAA8, reached from the DSP-message handler @0x4FE94: the 11th occurrence of a certain DSP message/error → update mode.

**Not covered.** A broken controller app (crashing before USB starts) is only recoverable through the bootloader's own logic, which is not in our files. That is what the hands-on button test is for.

**Tool.** `tools/pmmode.py` (read-only; sends only `12 30`) reports APP vs UPDATE mode once per second. Uses venv `tools/.venv` (mido + python-rtmidi, Python 3.13).

**Hands-on result (2026-11-17).** 8 power-ons with `pmmode.py` running: plain, Up, Down, Up+Down, knob held, Up+Down+knob, USB plugged in while holding.
- **All came up in APP mode.** No button combo tried enters update mode.
- With the pedal off and charging, it is **not visible on USB**, so the controller is fully off. Plugging USB in while holding buttons is therefore the same as a normal power-on.
- Holding Up during boot just scrolled presets once the app was running (events `12 1B 01` + `12 43 <preset>`).
- Conclusion: the only known ways into update mode are the app itself (`11 6F`) and the app's automatic DSP-failure fallbacks. **A broken controller app has no known recovery path yet.**

## 14. Header word @0x04 solved

`5868USB.dylib` `checkCrc` (x86_64 @0xBE810):
- `getFirmwareHeader`, then reads the whole file.
- Requires the file size to equal the header size field.
- Runs a table-driven CRC-16/MODBUS over **file bytes 0x06…end** and compares it with the u16 at offset 4.
- Stored big-endian: V1.3.3 = `24 AC`, CRC 0x24AC. **[confirmed]**

`isValidFirmwareFile` (@0xBD350) checks:
- magic `HTFW`
- the device name contains the header name (offset 0x0C)
- file size == header size

`pmfw.py pack` now recomputes this CRC; round-trip is still byte-identical. The first cut0 file was rejected ("not compatible") because this CRC wasn't updated.

## 15. Official recovery mode (from the Sonicake manual, found by the user)

- **With USB unplugged**, hold **◁ + ▷ + VALUE/VOL** until the screen lights.
- Then connect the **data** USB-C port (the one with the USB symbol; the other is charge-only) and run "Firmware Update" in Sonicake Manager.
- The controller app has no code path for this combination; its only update-mode entries are `11 6F` and the DSP-failure fallbacks. So it is the **bootloader's** check, and should work even when the app firmware is broken. **[inferred, to be confirmed by test]**
- Earlier test #5 failed only because USB was already connected.

**Incident 2026-11-17.** The pedal froze while the user saved a preset on the cut0 firmware. My `pmbackup.py` was retrying reads at the same time (stuck at 300 s). It was fixed by cutting power (battery). Most likely cause: concurrent USB reads during the flash write. `pmbackup.py` is now hardened: refuses to run while Sonicake Manager is open, has no retries, stops at the first 1.5 s timeout, and tells the user not to operate the pedal.
- **Confirmed 2026-11-17 16:30:** the button combination puts the pedal in bootloader UPDATE mode (handshake reply `11 30 01 01`). USB in that mode: vendor "Sonicake", product "Pocket Master", VID 0x84EF (34031), PID 0x0285 (645).

## 16. Cut 0 result (2026-11-17), done

- Modified firmware (2 text edits + recomputed section and file CRCs) was accepted by Sonicake Manager, flashed, and booted.
- **"Test Fuzz" showed in the DRV list**, so effect names come from the section-4 effect DB.
- **"RVB" → "TST" did not change the main screen**, so the block labels are images. The `RVB` string table entry is used elsewhere.
- Recovery mode (◁ + ▷ + knob, USB unplugged) confirmed to be bootloader UPDATE mode. Official V1.3.3 re-flashed from it. Grey Fuzz is back.
- Data check: all 100 presets, the preset name list, the IR and clone slot lists, and device info are byte-identical before (15:57) and after the round trip (16:37). The freeze/power cut lost nothing.
- Reference backups: `backups/20261117-155755`, `backups/20261117-163745`.
- Tool fix: `pmbackup.py` waits 0.5 s after opening the port (the first message was being lost), allows one calm retry per request, refuses to run while Sonicake Manager is open, and stops cleanly otherwise.

## 17. Cut 2: English patch built

`build/cut2/Pocket Master Firmware V1.3.3-cut2-english.bin`: the official V1.3.3 with two 4-byte code patches in the MCU app, plus recomputed section and file CRCs.
- CPU 0x4E598 (file 0x3E598): `slti $r1,$r0,#1` → `movi55 $r1,#0 ; nop16`. Language at boot = English.
- CPU 0x4DACE (file 0x3DACE): `slti $r0,$r0,#1` → `movi55 $r0,#0 ; nop16`. `is_cn_variant()` returns 0. Its 8 callers (UI code 0x1AE30–0x21818) choose between two near-identical drawing paths (CN vs EN layouts), so the pedal now uses the English layouts too.
- The factory config value itself is untouched. Reverting = flash the official file.

## 18. UI navigation internals (WinManager, CPU addresses)

- **Windows.** `@0x16330` registers window i (< 32) with 3 callbacks in a table at gp-16620 (12 B each). `@0x162E8` switches window: calls the old window's exit, then the new window's enter.
- **Per-window key map.** On entry, each window calls `WinMessageListRegister(list, n)` `@0x16358` (n ≤ 128). The list is `{u32 msg, u32 handler}` pairs, copied to gp-17644. 17 such lists were found, at callers 0x19986, 0x1A9CE, 0x1DD5C, 0x1FB6C, 0x1FF5A, 0x2024A, 0x211B0, 0x22E96, 0x23684, 0x238C0, 0x23C94, 0x23F0E, 0x24EBC, 0x262FC, 0x279A8, 0x28D26, 0x2A280.
- **Global map.** `WinGlobalMessageListRegister` `@0x163AC` (≤ 256 entries; one list at 0x134094, 37 entries). Key events → 0x2C5A4 (probably an idle/auto-off timer reset), plus system messages `0xNNB010` (BT, USB, battery…).
- **Message format.** `msg = class | key << 8 | event << 16`; class 0x02 = key, 0x03 = window refresh. Posted via `@0x16400` into a queue (gp-46176).
  - Key events come from `@0x2C260`: `key = (raw & 0x80) | map[raw & 0x7F]`, map at 0x134074 (raw 6→0, 15→2, 31→1, …).
  - Keys seen in window maps: **0x00, 0x01, 0x02, 0x80, 0x82**. Events seen: **1, 3, 4, 5, 6** (6 only for key 2). Likely meanings: 0/1 = ◁/▷, 2 = knob push, 0x80/0x82 = knob rotation; events = press / click / long / repeat / double-click. **[unconfirmed mapping]**
- **Submenu windows** register only a handful of events, and none maps to "go to parent". "Back" is missing by design, not a bug. Adding it means changing these per-window lists and adding a small "open parent window" handler.
- **Update mode from the UI.** No menu item exists. The function that enters update mode (`@0x50790`) can be called from a new Settings item.

## 19. Saved settings: language and brightness (CPU addresses)

- **Settings struct** at gp-11100, saved to flash when the dirty flag at +0x24F is set. **+0x0E = language** (0 EN, 1 CN), **+0x0F = brightness** (0–100).
- **Language.** Setter `@0x4E444` (stores +0x0E, `set_lang`, marks dirty); wrapper with app notify `@0x4FFB4` → `@0x4CA14(2, …)`. At boot, `@0x4E58C` **overwrites** it from the factory config, so a saved choice never survives a reboot. Cut 2 forces 0.
- **Brightness.**
  - Driver `@0x50F54(level ≤ 100)` sets PWM channel 4 via `@0x702F4`. Getter `@0x4E460`. Setter `@0x4E468` (clamps to 100, stores +0x0F, applies, marks dirty). Wrapper with app notify `@0x4FFDC` → `@0x4CA14(3, …)`.
  - Uses: factory-test "Screen Light" screen `@0x28C2C` (knob changes level in steps of 1/5 and prints "Light:%d"); two windows set 100 on entry (`@0x238D4`, `@0x23CA8`); `@0x1FB30` sets 100 then dims to 20 (probably the screensaver/standby screen).
  - A message handler `@0x4B8A0` takes a value from the message payload and calls the notify-setter. That is probably the phone app's remote brightness setting **[inferred]**.
- **No user menu exists for either.** Both could be added as Settings items that call the existing setters. For language, the boot code must also be changed to keep the saved value.

## 20. Uploader built (`tools/pmflash.py`)

- `check <fw.bin>`: offline. Validates the file and builds the exact frame stream. For the official V1.3.3 the stream is **byte-identical to the captured official update (108,274 frames)**. For the cut2 file only the 2 frames carrying the patches differ.
- `flash <fw.bin>`:
  - Refuses while Sonicake Manager runs; requires typing FLASH.
  - Sends `11 6F` if the pedal is in app mode, then re-opens the port.
  - Stop-and-wait: every frame must get `14 08 00` (`14 08 01` is accepted only for the `11 69` version announces, as in the capture).
  - Aborts on the first missing or bad ACK, leaving the pedal in update mode.
  - **Not yet run against the pedal.**

## 21. Cut 1 progress: DSP module calling convention (sec0, partial)

- Module table pointer at RAM 0x20002350 (`+0x13` = group count, `+0x14 + 4·g` = per-group list). The pointer to the currently loaded module header for each group is at **0x2000382C[g]** (11 entries).
- **Load** `@0x4EE4(group, index, slot_desc)`: picks the blob, copies code to the slot's RAM base and state to the state region (`@0x4A4C` / `@0x48CA`), and records the header pointer.
- **Param update** `@0x4F70(group, args)` → calls header **entry0** (`+0x10`) as `entry0(float *params8, &extra)`.
  - Caller `@0x6574` passes `params = 0x20002AF4 + 0x1A0 + 32·g` (8 floats per group, the same 8 values as preset tag 0x3004).
  - `extra` = `60000 / BPM` (tempo in ms). For CAB it is `@0x6F0C(IR slot)`; for CLONE it is `@0x8378(clone slot)`.
- **Process** `@0x4F90(group, ctx)` → calls header **entry1** (`+0x14`) as `entry1(ctx[0], (u16)ctx[8], ctx[0xC], ctx[4], &ctx[0x10], &ctx[0x14], &ctx[0x18])`.
- Audio loop (RAM, around 0x20000E80–0x20001030):
  - **block = 64 frames, float32, stereo-interleaved (L,R)**, i.e. 1.45 ms per block at 44.1 kHz, ≈ 278,600 CPU cycles per block at 192 MHz.
  - Walks the chain order (veneer 0x2000008C); groups 2/9/5 get special handling (DRV + CLONE + EQ path).
  - Per block it calls process for each enabled group via veneer 0x200000AA.
- Still to pin down: the exact meaning of each `ctx` field (in/out buffer, frame count, bypass/mix byte, enable), the module's return value, and how `extra` is used.

**Cut 1, important finding: modules are mostly parameter → coefficient generators.**
- Red Fuzz (DRV #6, base 0x10002800, state at 0x2800064C):
  - `entry0 @0x10002850(float *params)` clears its state and writes constants/biquad-like coefficients plus Fuzz/100 and VOL/100.
  - `entry1 @0x10002910(buf, n, params, …, &enable_byte)` only re-reads two knob values and copies the enable byte into state[0]. **It never touches the audio buffer.**
- AMP #0 TWD Deluxe `entry1 @0x10003A4C`: knobs → polynomial tone-stack coefficients written to state at 0x28000EB4. Also no per-sample loop.
- So the actual per-sample DSP (filters, waveshapers, convolution) runs in **generic engines in the kernel / shared code**, which read each group's state layout. Bigger modules (CLONE: 42 loops, 85 FP MACs) may contain their own processing.
- Consequences:
  1. For **Cut 1** a load-test module just has to busy-wait in `entry1` (called every 64-frame block).
  2. For **Cut 3**, new algorithms either fit an existing engine (coefficients only) or must process `buf` themselves. Whether a module may write to `buf`, and in what order the kernel engine runs, still has to be verified.

## 22. Audio measurement chain works (2026-11-17)

- Path: Mac headphone jack → cable → pedal **IN** → effects (preset P08) → pedal USB audio → Mac. `tools/pmaudio.py jack <s>` plays a 1 kHz −20 dBFS tone and records.
- Result: tone recorded at about −25 dBFS. THD 44–88 % (P08 distorts, which proves the signal went **through the effects**). **0 dropouts**, which is the baseline for the load test.
- **Recording via PortAudio/sounddevice returns pure zeros from this device**, while ffmpeg (AVFoundation, device "Pocket Master Audio") records correctly. `pmaudio.py` now records with ffmpeg.
- USB playback (Mac → "Pocket Master Audio" output) goes to the pedal's OUT mix and does **not** pass through the effects.
- The pedal exposes no CoreAudio volume or mute controls: output level is set by Settings → USB → Monitor, recording level by FX REC (0 dB = unity, up to +20 dB).

## 23. Cut 1 load-test firmware built (not yet flashed)

`build/cut1/Pocket Master Firmware V1.3.3-cut1-cputest.bin` = the cut2 English firmware plus:
- **Section 1, DRV #7 blob (was Bass Drive, offset 0xE020, span 0x11B4) replaced** by: header (0x24) + [Red Fuzz code 0x148 B, zero pad to 0x200, our load-test code (`cut1/loadtest.c`, 632 B, linked at 0x10002A00)] + Red Fuzz's initial state (0x338 B).
  - Blob layout confirmed for all DRV/AMP/FX1 modules: `blob = header + code (total bytes) + initial state (state_size bytes)`.
  - Entries point at our wrappers (0x10002A01 / 0x10002A1D), which call Red Fuzz's original entries. Slot RAM used 0x10002800–0x10002C78 of 0x10003800.
- **Section 4 effect DB:** "Bass Drive" (DRV list) renamed to "CPU Test 1" (same length).
- **Module behaviour:**
  1. Enables the DWT cycle counter and measures the normal block period (plausibility check 100k–1M cycles; otherwise does nothing).
  2. 3 cycles of: marker (one block +150 % burn), 2 s rest, ramp +1 % of block period every 0.25 s, stop after 2 consecutive periods > nominal + 14 % or at 100 %, 4 s rest.
  3. Burn is capped at 2 blocks, and the busy-wait has an iteration guard (never hangs).
- **Measurement:** `tools/pmloadtest.py run` plays 1 kHz into the pedal and records USB for 110 s. It finds glitch clusters (envelope dips or 2nd-difference clicks) and pairs marker → overload. Validated on a synthetic recording.

## 24. Cut 1 run log (2026-11-17)

- 18:12 flash of cut1 started; it was interrupted by the session (pedal left in UPDATE mode). 18:15 re-run: **DONE in 176 s**, every frame ACKed.
- After DONE the pedal did **not reappear on USB** (checked for > 4 min: no USB device at all in ioreg / system_profiler). After earlier flashes it re-enumerated within ~20 s.
  - Unknown whether it is switched off, hanging at boot, or stuck before USB init. The cut1 changes affect only the DSP module blob for "Bass Drive" (DRV #7) and its name; the MCU app is identical to cut2.
- `tools/cut1_auto.py` is running in the background (log `logs/cut1-auto.log`):
  - When the pedal shows up in **app mode**, it runs the CPU test unattended: writes the test preset into P100 (a duplicate factory slot, backed up), records, analyses, restores P100 byte-identical, and re-selects the original preset.
  - If it shows up in **update mode** (cut1 doesn't boot), it re-flashes the known-good cut2 English firmware.
- **Architecture insight while waiting.** The module "state" lives in the 0x28000000 region, next to a peripheral at **0x28008000** that the kernel starts and polls (`@0x10280`, `@0x1029A`: writes inputs to 0x28000000 + 0x13·4…, reads results from 0x28000000 + 0x93·4…). This looks like a **hardware audio accelerator** (filter/FIR engine) with coefficient RAM at 0x28000000. Small modules like Red Fuzz only write coefficients there, and the hardware does the per-sample work. **[inferred]**

## 25. Cut 1 result: first real CPU headroom measurement (2026-11-17 19:40)

**How the earlier runs went.**
- Tests driven by writing and selecting a preset from the Mac (P100) never loaded our module.
- Selecting the effect on the pedal and saving P08 does load it, and the module then runs **every audio block** (probe: on/off toggled every 345 calls = 0.5 s).
- The DWT cycle counter is not usable (cut1d ramp produced no load).
- cut1e uses **SysTick** (kernel runs it at core clock, reload 0xFFFFFF) for timing and overrun detection.

**Recording** `audio/20261117-194049-cputest.wav`. Preset P08: NR, AMP, IR, FX2 (comp), RVB on, DRV = test effect, DLY off.
- Three clear degradation episodes, 18 s apart (= one test cycle each).
- Cycles 2 and 3: **audible level dips start at ~35–36 % extra load per block; the module's overrun detector trips at ~47–48 %.**
- Cycle 1 overlaps the power-on/preset-load dropout and is not reliable.

**Interpretation.**
- With this preset about **35 % of each 64-frame block is free before audio quality suffers**: ≈ 97,000 cycles per block, ≈ 1,500 cycles per sample at 192 MHz.
- Hard overrun is at ≈ 47 %.
- Usable budget for new processing: ~30 % with a safety margin.
- **NAM A2-Lite** (estimate ~1,640 cycles/sample in int16) does **not** fit on top of this chain. It might fit if it replaces AMP + CAB (as Clone does), which frees their share. That needs a measurement with AMP/CAB off.

**Next measurements.** The same test with (a) a heavy preset (DLY + RVB + modulation on) for the worst case, and (b) AMP + CAB off, to see what they cost.

## 26. Cut 1 variant results (2026-11-17 19:53–19:57, analysed by hand; markers give exact ramp starts)

| Variant (blocks on) | Audible dips start at | Overrun at | Notes |
|---|---|---|---|
| P08: NR DRV AMP IR FX2 RVB | ~34–38 % | ~47–50 % | 2 runs × 3 cycles |
| AMP off: NR DRV IR FX2 RVB | ~38–39 % | ~51 % | markers visible at 22.5 s / 40.5 s |
| All on: NR FX1 DRV AMP IR EQ FX2 DLY RVB | ~23–26 % | ~43–50 % (episode ends inflated by delay echoes) | delay repeats the dips; more than 3 cycles appeared (module re-initialised) |

**Conclusions.**
- The **amp block costs only ~3–4 % of the CPU**. Most per-sample work (amp, cab, filters) evidently runs on the hardware audio accelerator. The CPU limit (~48–51 % extra load before overrun) barely depends on which blocks are on.
- **Guaranteed free CPU:** ~24 % with every block on, ~35 % with a typical preset. As cycles per sample at 192 MHz: ≈ 1,040 (all on) to ≈ 1,500 (typical).
- **NAM A2-Lite** (int16 estimate ≈ 1,640 cycles/sample) **does not fit** in the amp position, even with the amp off (~38 % ≈ 1,650 cycles, no margin). A smaller NAM-style model, or offloading parts to the accelerator, would be needed.
- Restored afterwards: P08 written back byte-identical (`cut1/p08-before-variants.bin` = test variant). The user's original P08 is in `backups/20261117-163745`.

## 27. Measurement fix: ffmpeg drops samples (2026-11-17 23:00)

- ffmpeg/AVFoundation recording of "Pocket Master Audio" **loses ~7 % of the samples** (20 s requested → 18.6 s of audio; a 1000 Hz tone reads 998 Hz, and every pure tone shows sidebands every ~26 Hz from the gaps).
- PortAudio callback recording (`pmaudio.record`, `InputStream` with `latency="high"`) is gap-free (20.0 s, no sidebands). All tools now use it. Earlier "PortAudio returns zeros" was the blocking `sd.rec` path at the time.
- Consequence: harshness and timing results from recordings before 23:00 are suspect; the first effect audit was redone; the Cut 1 headroom matrix is being re-run (§29).
- **Flashing:** after DONE the pedal shows a reboot dialog; tap OK immediately, otherwise it switches itself off (explains the earlier "did not reappear on USB" cases).

## 28. Cut 3 probe results (firmware cut3d, "CPU Test 2" in DRV, Treble = 0 → probe mode; 2026-11-18 00:01)

Decoded from `audio/20261118-000134-bench.wav` (values sent as zeroed-audio dips, all 26 frames valid):
- **CPU: CPUID 0x410FC241 = Cortex-M4 r0p1**, DSP extension present (ID_ISAR3 = 0x1131). SysTick = 192.0 MHz (block period 278,624 ticks = 1.4512 ms).
- `entry1(arg0 = 0x20006300, n = 64, arg2 = 0x20002CDC (params), arg3 = not a pointer, arg4..6 = 0x20006718/1C/20)`. arg0 holds float audio (peak 0.154 for our test tone).
- **A module can change the audio**, but arg0 is not "the current block": zeroing arg0[0..64) gives short gaps (8–24 samples) roughly every 640 samples, not silence. arg0 is most likely a fixed position in a larger ring buffer. To process audio properly we still need the ring's base/size/write index (next RE step: the audio loop around 0x20000E80).
- **Benchmark (code + data in the DRV slot RAM 0x10002A00, minimum over 64 blocks, SysTick ticks):**

  | Kernel | Measured | Ideal Cortex-M4 |
  |---|---|---|
  | float MAC (both operands in slot RAM) | **12.7 cycles** | ~2 |
  | float MAC, weights in SDRAM (0x29040000) | **29.3 cycles** | – |
  | int16 MAC via SMLAD (2 MACs/instruction) | **6.9 cycles per MAC** | ~0.5–1 |
  | rational tanh (1 divide) | 41 cycles | ~20 |
  | biquad, per sample (5 MACs) | 31 cycles | ~10 |

  Code in the 0x10000000 slot RAM runs ~4–6× slower than an ideal M4 (wait states on that bus, or bus contention with the audio accelerator). SDRAM reads add ~16 cycles each.
- **Consequences:** NAM A2-Lite (1,731 MACs/sample) would need ~12,000 cycles/sample even with SMLAD, ~3× the whole DSP → **not possible**. Budget for a new effect at ~650 cycles/sample (worst case) ≈ 50 float MACs/sample; ~1,500 (typical preset) ≈ 120. A 2× oversampled circuit-style drive (~30 MACs + 2 tanh per oversampled sample) ≈ 900 cycles/sample: fits a typical preset, not the worst case, unless code can run from faster RAM (open: try code in 0x20000000 kernel RAM).

## 29. What the community CFW 1.0.2 does internally (local analysis only, nothing redistributed)

File `../PocketMaster_CFW1.0.2_base1.3.3.bin` (sha256 aeb5e974…). Built on stock V1.3.3; all 5 sections changed:
kernel +10.7 KB (49 patched spots + appended code), modules +4 KB but heavily rearranged, cab catalog +4 KB (10 IR slots),
MCU app +50 KB (UI, MIDI, scenes …), effect DB rewritten (new names/knobs).

- **DSP image layout:** module blobs are addressed by the DSP right after the kernel image (CFW: module section at DSP
  0x13000 = 0x4000 + kernel size, rounded). CFW entry addresses like 0x265F9 = module-section offset 0x135F8 + 0x13000.
- **Space trick:** many blobs now have `code_size = 0` and an entry0 thunk running *in place* from the module image:
  `adr r2,{src,size}; b.w loader` — the loader copies the real code into the slot RAM, then jumps. This frees the
  section space for the 16 Smart Box amps (AMP 22 → 38), FX1 15 → 27, FX2 17 → 29, EQ 3 → 7, DLY 9 → 24, RVB 10 → 15.
  So the 0x13000+ region is **executable**; their small wrappers (tempo sync, etc.) run there.
- **Tempo sync:** every modulation/delay entry1 is wrapped: `addw ip,pc,#4; b.w 0x50EA0; .word real_entry1, knob_info`.
- **How a module processes audio (their new A-Chorus, FX2 slot):** `entry1(buf, nframes, params, …, &enable)`;
  `buf` = **nframes stereo frames, interleaved float L,R** (stride 8 bytes), processed **in place**; the effect keeps
  its own 1024-sample delay line in slot RAM. Code still runs from slot RAM 0x10009xxx.
- **Consequence for our cut3 probe:** in the DRV slot, arg0 is *not* the interleaved block (DRV/CLONE/EQ have a special
  path in the audio loop, §21). Our "zero the first 64 floats" only produced sparse gaps for that reason.
  **Custom per-sample effects belong in FX1/FX2 (or DLY/RVB), not DRV**, unless the DRV path is understood.
- **Load meter / freeze protection:** no SysTick/DWT-CYCCNT literals added; probably the stock DWT profiler
  (§9, DWT CTRL ref at 0x10390 in both). Not traced further.

## 30. Incident 2026-11-18 01:35: cut4a (CFW 1.0.2 + appended test module) did not boot

- Flash completed (all 112,048 frames ACKed). Afterwards: no screen, not even the charging screen, no USB device.
- Recovered: reset + ◁ + ▷ + VALUE/VOL at power-on (USB unplugged) → bootloader UPDATE mode → flashed cut3d →
  app mode at 01:53. P08 read back byte-identical, presets intact.
- **Most likely cause: DSP image size.** kernel + module section: stock 0x5568C, CFW 0x58FE0, cut4a 0x59AC4.
  The CFW stops 0x20 bytes short of 0x59000 (both of its DSP sections end in …FF0), which looks like a fixed budget
  (MCU-side buffer or DSP RAM). cut4a was 0xAE4 over it; the MCU hanging before the display is consistent with a
  buffer overrun while it handles the DSP image. **Rule: never grow kernel + modules beyond 0x59000 bytes.**
  Not proven; the unmodified CFW has also never been booted on this unit.
- cut4b (`build/cut4b`): same size as the CFW (no section grows). The probe overwrites the CFW FX1 #15 'C-Wah' blob
  inside its own footprint (renamed 'CTest'); DRV #7 = CPU ramp as before. 6,398 bytes changed in the module
  section and 14 in the effect DB; nothing else differs from CFW 1.0.2.
- **02:01 unmodified CFW 1.0.2 boots on this unit** (app mode, P08 intact).
- **02:05 size test: CFW 1.0.2 + exactly cut4a's growth (0xAE4 zero bytes appended to the module section, nothing
  else) also boots.** So the plain size of the DSP image was probably *not* what killed cut4a (unless zero bytes
  overrunning a buffer happen to be harmless). Remaining suspects in cut4a: the relocated FX1 lists (module table
  and effect DB, 27 → 28 entries), the new DB record in the DB's padding area, or the new FX1 blob itself.
  cut4b avoids all of these (in-place replacement, no list or count changes).

## 31. How the CFW hooks the DSP kernel (load meter / freeze protection path)

- The kernel's RAM-code block (0x20000000, copied from image 0xE3D0) has 5 patched spots: four call veneers
  (0x20000064, 0xC8, 0xDC, 0x136) now point to rewritten kernel code or to code in the module image, and the
  **accelerator run-and-poll routine at 0x20001ECA** (the one that writes 0x28000000+0x13·4 and polls the results
  at 0x93·4) is replaced by a jump to appended kernel code at 0x12F20.
- That stub checks a RAM flag (0x20002AEB), then a magic **"CFWG"** at DSP 0x482D8 (module section offset
  0x352D8; header: magic, version 0x10001, load address 0x482D8, size 0x1484, "CFW0.8.2.1", function table at
  +0x20). If valid it jumps into that blob, otherwise it runs the original routine. So the CFW runs part of its
  audio-path code **in place from the module image region**, i.e. that memory is executable and fast enough for
  the per-block path (to be measured by the cut4b probe).
- The CFWG blob uses kernel RAM at 0x20002AFE/2C00/2D00/3004/4850/4E00/4F10/24C4 (unused parts of the kernel's
  zero-init area, 0x200023BC–0x20006AE8) and ICSR (0xE000ED04, pending interrupts) — consistent with measuring the
  time spent waiting for the accelerator (= load meter) and deferring work under overload (= no freeze).
- Kernel region 0x0AFA8–0x0E33D (13 KB) is rewritten (their optimised engines: reverbs, pitch, looper).

## 32. cut4b on CFW 1.0.2: boots; FX1 probe results (2026-11-18 03:57)

- cut4b booted (pedal parked on F01 before the flash). Risky tests ran without a crash (flags = 7).
- **A module can change the sound:** FX1 entry1 gets `buf` = 64 interleaved stereo float frames at 0x20006518;
  scaling the left samples by 0.5 lowered *both* outputs by exactly 6.0 dB, scaling the right samples did nothing
  → the chain is effectively **mono (left)**, duplicated to both outputs.
- Report decoding needed run-length decoding: the module is skipped in some blocks, so slots stretch.
  Values confirmed by both decoders are marked ✓.

  | Kernel (1024 float MACs) | Cycles per MAC |
  |---|---|
  | code + data in FX1 slot RAM ✓ | **12.8** |
  | code in slot RAM, data on the stack (0x2000xxxx) ✓ | **9.1** |
  | code executed in place from the module image, data in slot RAM ✓ | **9.3** |
  | code copied to the stack (run-length decoder only) | 16.6 |
  | A2-shaped layer (3 ch, 6 taps), int16 SMLAD + LUT, slot RAM ✓ | **829 cycles per sample per layer** → ×23 ≈ 19,000 cycles/sample |
  | same, float (run-length decoder only) | 1,300 → ×23 ≈ 30,000 |

  Every memory is far from an ideal M4 (≈2 cycles/MAC); the best seen is ≈9. **NAM A2-Lite needs ≈16× the
  worst-case budget, a 2-channel A2 ≈7×, an 8-unit LSTM ≈3×: no neural capture model fits on the CPU.**
  Captures must stay on the accelerator (clone engine). Circuit-style drives (≈70 MACs + LUTs per sample at 2×
  oversampling, ≈750–900 cycles) fit.

## 33. The co-processor ("engine") is a programmable DSP; module "state" blobs are its programs

- Control registers at 0x28008000 (+0x00 start/handshake, +0x40 status: bit1 busy, bit0 done ack, +0x48 a counter
  the kernel stores as current/max at 0x20002390/94 = the stock load profiler). Data RAM 0x28000000-0x28007FFF.
- Per block (kernel @0x1029A): wait idle, copy 64 L/R samples into engine RAM words 0x13.. and 0x53.., start,
  read results from words 0x93.. and 0xD3...
- Order in the audio loop (@0xF6xx): CPU modules NR, FX1 → **engine block** (the kernel runs the DRV, CLONE and
  EQ group handlers, then calls the engine once) → FX2, DLY, RVB on the CPU. So DRV/AMP/CAB/EQ/CLONE run on the
  engine; their ARM entry functions only compute parameters (that is why a DRV module cannot touch the audio).
- The per-module "initial state" that the loader copies to the 0x28xxxxxx state slots is **engine code**: 32-bit
  words with a small set of recurring opcodes (0x70060000, 0x50080010, 0x75060193, 0xE6520000, 0x96080001,
  0xA008xxxx …) plus float constants. Program sizes: Red Fuzz 206 words, Scream 341, TWD Deluxe amp 375,
  cab 467, GT EQ 93, clone 840.
- ARM-side amp parameters go to fixed engine RAM addresses (TWD: 0x28000E60.. biquad sets {b0,b1,b2,1,a1,a2}
  in 40-byte records, a 160-byte table copied to 0x28001068, tone stack to 0x28000EB4). Cab uses 0x28001600.
- Consequence: new amp/drive/cab/capture algorithms on the engine need its instruction set (custom, unknown).
  Work package: statistical ISA recovery from ~60 known programs (stock + CFW Smart Box amps), then on-device
  tests that change single words and measure the audio.

## 34. Results 2026-11-18 05:00-05:40 (CFW 1.0.2 base, hands-free flashing)

- **Boot protection off** from the Mac (global setting 0205 = 0, verified by read-back); flashes now reboot
  without the "POWER ON?" prompt (cut5, cut6 came back unattended).
- **CPU headroom on CFW 1.0.2** (cut4b, gap-free recorder): MAX preset 46.0 % free at overload (stock 36.8 %).
- **Our own engine code runs.** cut6 patched the Bass EQ engine program (words 4-10: x0.5 then jump to the volume
  stage). Measured: Bass EQ −6.1 dB flat vs EQ off / GT EQ 1 −0.0 dB. ISA decode (cfw/isa/FINDINGS.md) confirmed.
- **Engine load counter** (kernel copy of 0x28008048 per block, combo2 probe in DRV #7):
  Red Fuzz program only 8,230; + TWD Deluxe 46,283; + TWD + cab 110,009; Flyman B1+ 49,537;
  Calif DualM + cab + EQ 143,905; kernel max since boot 148,170. Cab (512-tap convolution, 32,768 MAC/block)
  ≈ 64,000 units → ≈ 2 units per MAC. Budget (units per block) still unknown → cut7 engine ramp.
- cut5 DS-1+ on the pedal was broken (output only 17 % harmonic): the firmware calls entry0 (parameter update)
  repeatedly and our entry0 re-initialised all filter states. Reproduced in the Unicorn ARM emulator
  (tools/armemu.py: harmonic fraction 1.00 → 0.65 with entry0 every block). Fixed: entry0 only updates parameters.
- Smart gate (NR slot) works: unity when open, silence in the noise floor.
- Capture fidelity experiment (tools/namfit.py, real A2 capture, 60 s real DI): NAM's own small submodel ESR
  0.024 vs the full model; best Wiener-Hammerstein fits: 1 stage 0.36, 2 stages 0.29 (quick torch fits).
  → better captures need a NAM-like network, not more filter stages.

## 35. Engine capacity, CPU cost of our modules, decisions (2026-11-18 08:00-08:30)

- **Engine capacity ≈ 270,600 counter units per block.** cut7 busy-loop in the Bass EQ program (code word 0xE05
  rewritten from the ARM side): the counter rose from 110,662 (TWD + cab) and stopped at 270,650 with no CPU
  overrun up to 1.04 M loop iterations → the engine is cut off at a per-block deadline (≈ the 278,600-cycle block
  at 192 MHz). Heavy preset (high-gain amp + cab + EQ) uses 143,905 (53 %); TWD + cab 110,009 (41 %).
  Free on the engine: ≈ 125-160 k units per block. Overrunning the engine does not stall the CPU (no freeze risk),
  the remaining engine stages are simply not executed.
- **Why DS-1+ (FX1, CPU) sounded wrong:** cost. ARM emulator count: 63,000 instructions per 64-frame block for the
  4x-oversampled model (≈ 985 per sample); at the 3-5 cycles per instruction measured for slot RAM that is
  70-110 % of a block → overruns. The gate costs 4,342 instructions per block (fine).
  Debug run confirmed the firmware calling convention: entry0 once, entry1 c = param array 0x20002CB4, n = 64, e = 1.
- Offline quality vs cost (DS-1 model): 4x + ADAA on both stages −66..−75 dB; 4x, ADAA on the diode stage only
  −35..−67 dB; 2x + ADAA −36..−44 dB; 2x no ADAA −20..−42 dB; stock JP Dist −8..−21 dB.
  TS808 model (4x + ADAA): −58..−78 dB (stock Scream −19..−42), classic mid hump (−11.5 dB at 125 Hz, peak ~1 kHz).
- **Decision: drives belong on the engine** (DRV block is engine-processed, the engine has 125-160 k spare units per
  block, the CPU has ≈ 25 % usable). Next step: a small assembler + reference emulator for the engine ISA,
  validated against the stock JP Dist / EQ programs, then a DS-1 engine program replacing JP Dist's.
- NAM A2-Lite on the engine: compute borderline (≈ 220 k units + activations), **memory impossible** (engine data
  space 4096 words = 16 KB; A2-Lite history ≈ 76 KB). A purpose-built small WaveNet (≤ 4 k floats incl. history,
  ≈ 70 k MACs/block) fits; my quick distillations did not converge (ESR 0.6) → needs a proper training pipeline.
- USB re-amp via setting 0403 did not work with the method tried (0403 already 1, no signal); not pursued.
- Daily firmware for the pedal: CFW 1.0.2 + smart gate in the NR slot only (build/daily, 2,804 bytes differ).

## 36. Engine ISA measured on the pedal, engine cost table (2026-11-18 10:30-11:25)

- cut8 / cut8b instruction probe (cut1/combo4.c, DRV #7 host, results sent as tones): ISA now decoded, see
  cfw/isa/FINDINGS2.md. Model tools/engine_emu.py agrees with every deterministic run; assembler tools/easm.py.
  Key finds: rsqrt macro, integer/bit ops incl. 16-bit half modes, flags in r15 (negative/zero) + conditional skips
  (min/max/clamp possible), code-RAM table loads, vector add/mul/dot. One class-9 form stopped engine audio until
  reboot (CAB-only, excluded).
- cut8c cost bench (cut1/combo5.c, logs/ebench.json), counter units per instruction (≈ engine cycles):
  plain ALU / fadd / fmul / ld / st / mov / bit ops 1; fmac 2; skip (not taken) 1.5; rsqrt 11; code-RAM load 7;
  vector ops ≈ 3 per element (dot64 196, copy64 197) - no faster than scalar code; taken loop branch ≈ 1-4.
  Capacity 270,600 per block ≈ 4,200 units per sample. Baseline with Red Fuzz in DRV: 8,077.
- Budget estimates: DS-1 at 4x oversampling ≈ 600 units/sample ≈ 38 k/block (14 %); LSTM amp hidden 6 ≈ 77 k (28 %),
  hidden 8 ≈ 115 k (43 %) - only instead of a stock amp program.

## 37. DS-1 / TS808 engine programs match the C models (2026-11-18 ~14:30)

- tools/drives_engine.py generates both programs (4x oversampling, ADAA diode clipper); tools/drives_unit.py tests
  each building block, tools/drives_ref.py is a float32 Python copy of ds1.c with per-stage comparison.
- Result in the engine model vs dsp/host: DS-1 max rel err 3.3e-5, TS808 4.1e-5 (float rounding level).
  Cost estimate: DS-1 48 k units/block (18 % of the engine), TS808 40 k (15 %). Program size 890 / 675 words.
- Bugs fixed on the way (all mine, none in the ISA model): loop pointer/counter kept in registers the clipper
  used as scratch; pointer spill slot inside the state area; sign of the clamp taken from |x|; inverted branch
  tests; stage-1 upsampler branch b used branch a's coefficients; a loop variable shadowed the model name.
- Process note: ~1 h lost repeating near-identical single-step probes instead of reading the generator and
  testing blocks in isolation. Unit tests per block + a Python reference with stage taps found the rest in minutes.
- LSTM amp (option B): first runs did not reach usable quality (best val ESR 0.61 at H8 with engine activations;
  NAM's own small model is 0.02). Needs a better training setup (longer, more data/augmentation) before it is worth
  flashing.

## 38. Why cut4a died: the DSP image cannot grow (bisect 2026-11-18 15:45-16:35, base = daily firmware)

| test | change | result |
|---|---|---|
| t2 | effect DB: FX1 list moved into the DB block's erased tail | boots, audio |
| t1 | module section: FX1 list moved to the END of the section (+112 bytes) | boots, NO audio |
| t6 | module section grows by 112 zero bytes only | boots, audio |
| t7 | module section: FX1 list moved into zero space INSIDE the section (no growth) | boots, audio |
| t5 | t1 + t4 (28th FX1 entry, data appended at the end) | flash hung, recovery needed (skipped later) |

- Conclusion: the DSP only gets the image up to its budget (kernel + modules about 0x59000 bytes; the CFW is 0x20
  short of it). Anything appended past that is not there at run time, so a list or blob placed there breaks audio
  or boot. Plain growth with zeros is harmless because nothing reads it (that is why the padding test passed).
  Moving lists and changing the DB is fine. **Rule: additions must fit inside the existing module section.**
- Also: build_cut zero-filled up to the next listed blob (cut9 silence); pmflash now ignores stale handshake replies
  and resends rejected data packets (recovered a half-finished update that way).
- Audio checks must use tools/audio_ok.py (all effects off, tone in); with effects on, the smart gate gives exact
  zeros when no signal reaches the pedal, which looked like "no audio" several times today.
- t8 (16:50): consistent 28th FX1 effect "C-Wa2" = list kept inside the module section (gate-slot zero space),
  entry 28 shares the C-Wah blob, DB record copied with its own effect id (C-Wah id + 1). Boots, audio OK;
  selecting C-Wa2 in P08 FX1 gives exactly the C-Wah result (-57.2 dB both, tone 220 Hz, params 50). **Adding an
  effect works.** Likely t5 also broke on the duplicate effect id and/or the appended blob.
- Effect id = first word of the DB record (group byte + index); presets store that id per slot.
- Space for new blobs inside the module section: only the 1,500-byte zero run (minus the list) plus blobs we retire.

## 39. Plan: our own amps, curated lineup (decided 2026-11-18 evening)

- Approach: measure the stock amps from outside (audio loop), fit our own gray-box amps (tube-stage curves,
  Yeh tone stacks, power stage), run them oversampled + ADAA on the engine. No stock-amp reverse engineering.
- Lineup (16): Twin Reverb (Dark Twin), Tweed Deluxe (TWD Deluxe), Bassman (B-Man B), AC30 normal (Voks 30N),
  AC30 TB (Voks 30TB), JC-120 (Jazz 120), JTM45 (Brit 45), Plexi (Brit 50), JCM800 (Brit 800), Mark IIC+
  (Calif IIC+), SLO-100 (Sol 100 LD), Friedman (Flyman B1+), Dual Rectifier (Calif DualM), 5150 (Halen 51),
  VH4 (Dizzy VH+), SVT (A BassVT, kept; no preset uses it). Other stock amps leave the menu (option b).
- Presets: none deleted. 7 factory presets re-pointed (same 7 in the user bank, which mirrors the factory bank):
  see logs/preset_remap.txt (F01 F10 F17 F19 F24 F46 F50). Knob values need translating per amp pair.
- Preset reading is safe over MIDI (12 4F <index>), no audio needed; logs/preset_amps.json = amp per preset.
- Install constraint: most stock AMP entries are 24-byte thunk headers (code_size 0) whose real code lives
  elsewhere in the module image; only Bog XT is a full blob (8188 code + 1680 program). Our shared amp code +
  per-amp wrappers must go into the space freed by retired amps (find it from the thunks' src/size pairs).
- Engine layout for the AMP block: program at code 1280..2815 (ends jmp 2816), data words ~920..1407.
- tools/amp_sim.py runs a stock amp offline (thunk loader works, engine program loads); left unfinished on
  purpose (stages repeat; not needed for the measure-and-fit approach).

## 40. Drives on the pedal, 2026-11-18 17:40-19:00 (one model per stock DRV slot, tools/build_drives.py)

- RAT (Dark Mouse slot) works on the pedal. Alias spikes (tools/alias_metric.py, ignores noise): at gain 50
  -59/-43/-35/-37 dB vs stock Dark Mouse -33/-27/-26/-21 (2.5/4/6/8 kHz). The old "harshness" metric is
  noise-dominated at high gain (pedal noise -41 dBFS at gain 100 for both).
- **Emulator and hardware disagree on some float/move encodings.** TS808 processed only ONE sample per 64-block
  (tools/block_pattern.py) until its post-stage fsub stopped using r2 as the second operand; now it works
  (alias spikes -58/-53/-47/-43). Fuzz still shows the one-sample pattern; DS-1 stops the engine until reboot
  (ARM side proven fine with a neutered program). Library position is not the cause (TS808 lib at 142/147/200 alike).
  Suspect forms (R,A,B) never executed by the working programs: fuzz fadd (2,8,2), fsub (2,8,8), mov r2<-r8;
  DS-1 fsub (8,10,9) in TRANS, fmul (2,9,2). Not address-related. Next: probe these exact words on the pedal
  with the cut8 harness (tools/eprobe_gen.py) before trusting more engine code (amps use the same library).
- Pedal left on build/drives-safe2 (RAT + TS808 replacing Dark Mouse + Scream; JP Dist, Shark stock).

## 41. All four drives work on the pedal (build/drives-all4e, 2026-11-18 ~21:00)

- Two hardware rules found by bisecting on the pedal (emulator does not model them):
  1. The skip-over-jmp loop tails (`skipeq ...,FIN / jmp SAMPLE` and `skipeq ...,DOWN / jmp CORE`) only loop
     correctly at certain code parities; otherwise the sample loop runs once per block (the "1 sample per block"
     symptom of TS808/Fuzz). drives2/amps2 now pad with a nop: core skip at odd, tail skip at even address,
     library at an odd address.
  2. The TRANS/CUBIC call path (call inside a call, skipbs on r15 after fsub) stopped the engine until reboot in
     the DS-1. Replaced by a biased symmetric ADAA booster (dsp/ds1.c DS1_TRANS_ADAA 2, same on both sides).
- Only encodings executed by the proven programs are used (tools/elint.py checks a program against them).
- On the pedal (alias spikes, tools/alias_metric.py, gain 50 / 100, 2.5/4/6/8 kHz):
  TS808 -63/-56/-50/-45, DS-1 -73/-67/-66/-65, RAT -63/-43/-34/-37, Fuzz -66/-57/-49/-42.
  Stock: Scream ~-25, JP Dist up to +45 (old metric), Dark Mouse -33/-27/-26/-21.
- Pedal output vs C model (tools/hw_vs_model.py, DI clip): ESR TS808 0.08, DS-1 0.13, RAT 0.009, Fuzz 0.02;
  level about 2x the model (input scale assumption off by ~6 dB, harmless).
- Amp captures of the 16 stock amps behind the lineup: audio/ampcap/ (4 knob sets each). First jcm800 fit diverged
  (ESR > 1): to be fixed.
- 2026-11-18 late: build/drives-km on the pedal. Red Fuzz dropped from both DRV lists (Bass Drive moves to index 6,
  works). A preset asking for a deleted effect id just bypasses that block (tested). Klon (Butter OD id, 3-knob
  record copied from TS808's) and Big Muff (Grey Fuzz id, record from Fuzz Face's) - blobs relocated by best fit
  into the Butter OD / Grey+Red space (module list entries point to them). Flashing rewrote the live presets from
  the image (factory re-points applied automatically). Alias spikes gain 50: Klon -69..-60, Muff -68..-52
  (stock Butter OD -33..-15, Grey Fuzz -32..-16). Pedal vs C model ESR: Klon 0.09, Muff 0.05.
- Cabs (build/cabs1 = drives-km + new catalog): factory cab IR = int32 taps, peak-normalised to ~0.99 * 2^23,
  up to 512 taps per 2 KB block (stock used 416, the high-gain 4x12s only 145 = 3.3 ms!), padding 0xFFFFFFFF.
  Block index = high half of record word 4. 16 records re-filled with TONE3000 IRs (irs/, build/cabs1/cabs.txt),
  names changed, effect ids kept. Verified on the pedal: measured spectra match ours (corr 1.00, 3 s settle needed).
- Cab knobs (Low/High cut) not done: the stock cab module has only VOL; needs a wrapper that re-filters the taps
  after load (zero engine cost) - follow-up. Mic choice = the A/B/C entries.

## 42. All 16 amps on the pedal (build/amps16c, 2026-11-19 morning)

- One shared copy of the amp code (dsp/amp_core.c, 6.9 KB, in Bog XT's old blob space) + per-amp blob (stub with
  settings + engine program, ~1.7 KB) in module space only the retired amps used (logs/amp_reads.json from tracing
  every stock amp's loader). 22 stock amps dropped from both lists; factory presets using them re-pointed.
- Engine cost: 2x preamp oversampling for 2-3 stage amps (63-74k units), 4x for the 1-stage clean amps (78k).
  RAT + amp + cab at 4x reached 100 % (broken blocks); with 2x the chain matches the model (ESR 0.12).
  Fitting at 4x and running at 2x costs ~0.05 dB of tone match (measured per amp offline).
- 2x needs filter corners below its Nyquist: amp.c clamps stage corners to 0.45 fs (jtm45 fit had a 49 kHz LP -> silence).
- A/B on the pedal vs stock (64 takes): tone diff median 1.7 dB (90 % < 2.8), our fizz median -47 dB vs stock -25.
  Gain-curve differences 5-10 dB on the clean/edge amps (Twin, Deluxe, AC30N, Bassman): the stock ones compress
  more at low input; JTM45 fit still the weakest (3-4 dB).

## 43. UI cut plan (user decisions 2026-11-19)
- Main screen: smaller preset name, whole chain visible (10 blocks in chain order, small icon of the effect in use,
  on = tinted, off = dim). Edit page: smaller block row, bigger top panel; effect picture instead of the name text.
- Icons: monochrome 1-bit line art, tinted with the block colour. Must say WHAT the effect does at a glance
  (meaningful > pretty): gate = wave cut below a threshold line, comp = squashed wave, wah = rocker pedal,
  chorus = two offset waves, tremolo = wave in a pulsing envelope, delay = decaying repeats, reverb = dense
  decaying cloud, octave/pitch = note + arrow, EQ = band sliders.
  Modelled gear is drawn as it looks in real life (user, 2026-11-19): drives = miniature of the real pedal's
  silhouette and layout (TS808 box with wide footswitch, Klon with its 3 knobs, DS-1 with the hinged treadle,
  RAT wedge, Fuzz Face round housing, Big Muff big box 3 knobs), amps = the real amp's front (tweed Deluxe,
  blackface Twin, AC30 diamond grille, Marshall head with plate, Mesa, 5150, Diezel...), cabs = speaker layout.
  Shapes only, no logos or brand text. Effects that copy a famous pedal may use its look too.
- Sizes ~48x32 (edit page) and ~24x20 (main screen chain), 1-bit: ~145 effects x 252 B = ~37 KB.
  Free MCU flash ~160 KB between app end (0x167F50) and the DB (0x190000) - verify unused at runtime first.
- Load bars (DSP + engine) replace the chip icon + %. Brightness, English/Chinese in the same cut. Attended only.
- Step 0: a preview sheet (PNG on the Mac) of all icons for approval before any firmware change.
- Cab Low/High cut (dsp/cab_wrap.c, run in place from the module image, filtered IR copy passed to the stock e0):
  correct in emulation, but on the pedal any non-zero cut gives +35 dB garbage (also with the 16-word header copied
  in front of the buffer). Shelved; pedal back on amps16c. The stock cab ignores params 1/2 and VOL in e0.

## 44. FX2 Octave / Pitch rewritten (dsp/pshift.c, build/fx2e, 2026-11-19)
- Stock: voices out of tune (220 Hz voice +37 cents, 880 Hz -19 cents), junk -24 / -32 dB.
- Ours: SOLA pitch shifter (drifting tap, correlation-chosen splice, 256-sample crossfade), exact ratio.
  Pedal: tuning 0 / +2 cents, junk -31 (Octave) / -34 dB (Pitch). Buffer 8 KB in FX2 slot RAM (0x10009600).
- CPU lesson: FX code runs ~5x slower than an ideal M4 in slot RAM; a 96-MAC/sample correlation burst overran the
  block (clicks at one block phase, junk -2 dB). Search is spread over 160 samples at 16 MAC/sample now.
  tools/block-phase click check: clicks concentrated at one position mod 64 = CPU overrun.

## 45. SDRAM for our reverbs/delays (probe, 2026-11-19 ~17:30)
- dsp/memprobe.c (temporarily in FX2 Detune's slot, build/probe4): pattern written at 0x29000000 + k*0x28000
  (k 0..50, i.e. up to 0x297D0000), checked every block; positive control mutes as expected.
- With a 1 s delay, a 100 % reverb and a chorus running, no tested block was overwritten; all of 0x29000000..0x297FFFFF
  is real, writable memory (8 MB SDRAM). Kernel static zero-init region = 0x29000000..0x290D7580 (861 KB).
- Plan: our buffers at 0x29400000..0x297FFFFF (4 MB), well away from the kernel's region. Not tested: the looper
  (needs the pedal UI) - test once with the looper recording before release.
- Effect DB record format (tools/dbrec.py): 16-byte prefix (count at +8, category string offset at +14), 24 bytes per
  knob [ffff][name off][min][max f32][step f32][default f32][index][ff][00][15], then strings.

## 46. Reverb engine cost on the pedal (timing probe, DWT cycle counter, 2026-11-19 evening)
- Our FDN reverb (4 lines at half rate, diffusion, half-band resampling): Hall 223,500 cycles per 64-frame block
  = 80 % of the 278,600-cycle budget; Room 74 %. Stock reverbs: a few % (CPU meter). Target was < 10 %.
- SDRAM from the ARM: ~33 cycles per read (random or sequential, no burst gain), ~20 per write. Most of the cost is
  compute (code runs ~5x slower than an ideal M4). Reaching 10 % needs ~8x less work = roughly stock quality.
- Decision rule (user): if the affordable version is not clearly better than stock, keep the stock reverbs/delays.
- CPU meter: reads the DSP load; RVB code is called even when the block is off (our entries must handle that).
- JTM45 refit on the pedal (safe1): tone diff 3.5-3.8 dB vs stock Brit 45 (was 2.8-4.0); small gain only.
- Pedal on build/safe1 (amps16g + Octave/Pitch, stock reverbs and delays).
- 2026-11-19 late: the "short stock reverb tails" were MY bug: the DB knob record has a parameter-index byte
  (+20 of each 24-byte knob block); Room/Hall/Church/Plate/Air/Dream read Decay from param 2, not 1. Re-measured
  (space_bench-stock2.json): Hall 1.6/3.1 s, Church 2.6/4.4 s, Plate 1 2.9/4.4 s, Room 0.5/1.0 s, Dream 2.8/5.2 s.
  Real remaining issue: tail colouration ~22 dB (metallic peaks) on most stock reverbs (Room/Air ~10-11).
  Same bug in the amp build: Halen 51 PRES = param 6 (fixed, build/amps16h).
- Delay engine (dsp/delay.c, 5 voices): 4-7 % CPU on the pedal once state is in DLY slot RAM (SDRAM state = 2x).
  Correct offline and in emulation, but on the pedal the Time value does not arrive as expected (e1's params have
  Time = 0; e0's array also does not carry ms) -> repeats at the full buffer length. Unresolved.
- Pedal on build/base2 (amps16h + Octave/Pitch), stock delays/reverbs.
- Delay decoding (dlp*/dl8-11): the CFW kernel has its own delay engine for the 9 Sonicake delay slots: calls go
  through its table at kernel 0x10910 (magic "FX8D" at 0x10900); slot s: e0 index 10+2s, e1 index 11+2s
  (generic e1 0x11E61 + per-type data). Patching those entries makes the kernel call our functions: e0's array has
  Time in ms (Mix as a fraction), e1's array has no Time. Our delay line then runs correctly inside (probe: y1 and
  the written samples carry signal, pos advances), but no echo reaches the output - the kernel evidently produces
  the delay output itself / discards our buffer. Unresolved; next step would be reading 0x11E61 offline.
- Pedal back on build/base2.
- DELAYS DONE (build/dl14): our engine in the CFW-added delay slots (normal modules, 24-byte headers): Shiny ->
  Digital, Flash -> Slapback, Float -> EP-3, Damage -> DM-2, Glost -> Echo+. Mag and Sweep dropped (presets F04 F10
  F21 F33 F43 re-pointed to EP-3 / Digital). Key facts: knobs only from e0 (e1's array has no Time); Mix arrives as a
  fraction; a Time that equals a note value is stored as a note index 0..10 (CFW table at 0x50F90: beats 4,2,3,
  4/3,1,1.5,2/3,1/2,3/4,1/3,1/4) times the tempo in ms passed through e0's 2nd argument.
  Pedal: correct repeat times, cost 5-7 %, Digital clean (repeat distortion -35 vs Pure -23 dB incl. noise,
  wobble 0.8 vs 4.9 cents), EP-3/DM-2 darker repeats (-2.6/-2.8 dB HF per repeat), slight stereo widening.

## 47. NAM capture -> pedal conversion (2026-11-20 early morning)
- tools/namrun.py: own numpy runner for A1 WaveNet .nam files (weight-count verified on 8 TONE3000 captures) and A2
  (namref). tools/nam2pedal.py fits our amp model (same code as the 16 amps, 2x, 63-75k engine units) [+ optional
  512-tap cab IR] to a capture rendered on 70 s DI + level ramps + noise. Alignment matters: NAM output leads ours by
  ~11 samples and is inverted for some captures (searched lag -64..96 and polarity, re-aligned during the fit).
- 5150 II (TONE3000 #35142): held-out ESR 0.55, tone 0.44 dB, gain curve 0.18 dB. On the pedal as a NEW amp entry
  (tools/add_nam_amps.py: AMP lists grow in place into the slack left by the removed amps, DB record cloned from
  Halen 51 with a new id 117440628): plays, 0.72 dB tone difference to the real capture measured on the pedal.
- Night test: pause/resume via logs/night/PAUSE (tools/night_ctl.sh); resumable (skips takes already logged).
  One false failure burst: the Mac's output got muted at 04:35 -> test now unmutes before re-flashing.
- Night-test "noisy" flags on amps/drives at high Gain/VOL are not a regression: the silence floor is input hum
  (strong line at 689 Hz = fs/64, present in the originals too) times the gain. Same captures (Gain 100, rest 50):
  originals -31..-44 dB, ours -45..-52 dB (6-15 dB quieter). Threshold for drives/amps is now -25 dB.
- NAM batch (amp-only, 1500 steps): held-out tone diff / gain curve: 5150 0.44/0.18, JCM800 0.97, AC30 1.01,
  Friedman 1.11 (good); Recto 1.57, Plexi 1.68 (gain curve 3.3), Twin 2.51, Deluxe 2.89 (alignment wanders, poor).
  build/nam4 = dl14 + 4 new amp entries (NAM 5150/Friedman/JCM800/AC30, ids 117440628-631, ~75k units each, sim
  rel err <1.1e-3). On the pedal vs the real capture: 0.71 / 1.35 / 1.97 / 1.40 dB. Menu display not yet checked.

## 48. Stock Clone ("Tone Catch") behaviour vs AMP/CAB (measured 2026-11-20 ~11:00, dl14, P08, empty clone slot 0)
- Clone = module 9, fx 0x0F000000+slot, knobs Gain/VOL/Bass/Middle/Treble; 5 user slots, all Empty on this pedal;
  no factory preset uses it. Sonicake Manager has Import/Export Clone (.clo) and converts .nam by re-capture.
- Clone on (empty slot) alone: clean pass-through. Clone + CAB: CAB is ignored (same level as bypass).
  Clone + AMP (with or without CAB): digital silence. -> the Clone replaces AMP and CAB (shared code/engine RAM);
  the .clo carries its own 512-tap FIR. No sign of amp-only vs amp+cab detection in the app or the format.
  Not yet known: whether the pedal's UI switches AMP/CAB off when the user turns Clone on.
- The rig1 pedal test (Recto808 amp + cab as amp/cab blocks) never ran: the wait loop hung because the night test
  had already finished. Also: at ~10:15-11:00 the pedal stopped streaming USB audio (exact zeros) while SysEx still
  worked; a re-flash/reboot fixed it. Cause unknown (idle? battery?).
- Direction from the user: NAM captures go into the Clone slots (user-loaded via Sonicake Manager), NOT as new amps.
  Goal = a terminal script .nam -> .clo that sounds better than the app's conversion, within the stock clone engine.
  build/nam4 / add_nam_amps.py are therefore not for release.
- Night test rounds 1-9 were INVALID: from ~05:45 the long-running test's PortAudio input failed to open
  (error -9986, after another process re-flashed the pedal and it re-enumerated) and take() silently re-read the
  last /tmp/night.wav (all 4,800 later takes = one identical file). Fixed: per-process file, deleted before each
  take, PortAudio re-initialised on failure, hard error after 3 tries. 470 valid takes kept (round 0); rounds 1-9
  need a re-run when the pedal is free.
- CORRECTION to the clone measurements above: enabling module 9 via the preset does NOT engage the clone (with a
  real clone in slot 5 the output equals bypass, 0.0 dB), so the "CAB ignored" result was meaningless. The user says
  the AMP slot has a Mode toggle (strings "Mode" / "Clone" / "Basic" in the MCU app, once each). Need the user's
  saved P08 in Clone mode to learn the preset encoding.
- tools/pmclone.py: list / upload <clo> <slot> <name> / clear. Round trip of the app's cloFile.clo is byte-exact;
  upload of it to slot 5 ("TEST app clo") worked (user allowed slot 5 for tests).
- Capture type: NAM metadata "gear_type" (nam/models/metadata.py: amp, pedal, pedal_amp, amp_cab, amp_pedal_cab,
  preamp, studio). 7 of 9 files are tagged. Audio fallback (energy 6-12 kHz vs 0.5-3 kHz on 12 s DI): amp-only
  -13.5..+7.4 dB, amp+cab -31.5 (tagged) and -35.5 (untagged "Fender Deluxe" = really a full rig, which is why its
  amp-only fit was poor). Threshold -22 dB.
- P08 saved by the user in Clone mode: enable bits AMP(3) + CAB(4) + CLONE(9) on, fx[9] = 0x0F000004 (slot 5),
  fx[4] = User IR 1. So Clone mode = AMP bit AND clone bit; Basic = clone bit off. Measured (dl14): clone (app
  .clo, slot 5) changes tone 10.8 dB vs bypass; IR after the clone works (V30 changed it 3.3 dB). The pedal rewrote
  the (off) delay Time 4 -> 500 in P08 on its own.
- tools/clone_sim.py: stock Clone module offline. entry0(params, &ptr) where ptr -> device .clo (reads 24..2692).
  The clone's engine program ends with a jump to the EQ slot (0xE00), not the CAB slot. ISA additions needed
  (engine_emu, [inferred], amp regression unchanged): djnz/call/ret flags 0x4000 = 16-bit field, 0x2000 = high
  half (clone packs a ring index + a count in one register); class F S=C = bit-reverse rR into rB, width imm[7:5]
  (128-point FFT). Still unknown: class 9 S=6 (4 uses, 2 per block). Status: the 128-tap first FIR behaves
  (delay 50 -> lag 55), the 512-tap second filter does NOT (delay 300 -> lag 5, residual -3 dB) -> needs pedal
  measurements (test clones in slot 5) to pin down. Small-signal gain with the app's params: ~3.8.

## 49. UI groundwork (2026-11-20, offline)
- **Screen: 160 x 128, RGB565, ST7735S-class controller** (init: sleep-out, B1-B5 frame rate, C0-C5 power, E0/E1
  gamma, MADCTL 0x68 = landscape + BGR, COLMOD 0x55). LCD write-command @0x50ABC, write-data @0x50B04, set window
  @0x50B84 (0..159 x 0..127, 320-byte line buffer), init @0x50C28. malloc @0x68D38, memset @0xDC050.
- **GUI library: LVGL-style image descriptors** {u32 cf:5|w:11|h:11, u32 size, u32 data ptr}; cf 5 = RGB565 +
  8-bit alpha (3 B/px). tools/ui_images.py exports all 107 (223 KB) to ui/export/ + ui/contact.png: block icons
  (dim + lit, 30-37 px tall), block labels, chip/CPU icon, battery, transport/loop icons, toggles. Callers of
  descriptors: 0x479B8 (54), 0x328F8 (21), 0x427B8 (11) = image-set functions [inferred].
- **Fonts:** LVGL fmt_txt fonts (glyph cb 0x43378, bitmap cb 0x43338 [file offsets +0x10000 = CPU]), 7 fonts,
  line heights 10, 11, 12, 16, 19, 24, 49. Descriptor list in ui/fonts.txt.
- NDS32 GCC 13.2 (C only) being built in docker container pmgcc (ui/build_gcc.sh) -> commit as image pmnds.

## 50. Clone engine identified on the pedal (2026-11-20, tools/clone_probe.py, slot 5)
- Probe: click, noise -25 dBFS, 220 Hz ramp -50..-3 dBFS, guitar DI; test clones made by pmclone.build.
  Two-tap test clones prove both filters are plain FIRs on the pedal: FIRa (128) tap spacing 50 -> 50, FIRb (512)
  spacing 300 -> 300 / 100 -> 100, ratios 0.47-0.48 for 0.5. Static (no dynamics: level steps recover at once).
- Model y = post * bqB( FIRb( sat( g * FIRa( bqA(x) ) ) ) ), sat = pm(1-exp(-pr v)) / -nm(1-exp(nr v)) with the
  .clo's 4 params, g = 2.8-3.3 at knobs 50 for x at pedal-recording scale (x = DSP input x 0.166 x 0.96, i.e.
  g ~0.48 at DSP scale). Engine's own linear path (knobs 50): flat to 4 kHz, -4.7 dB 8 k, -13.6 12 k, -36 16 k.
  Fit on the sine ramp ESR 0.002 (= take-to-take repeatability); on noise/DI the model is at the repeatability
  floor (take-to-take ESR 0.11 noise, 0.33 DI, the high-gain clone amplifies the input hiss).
  tools/clone_sim.py (emulator) still wrong on FIRb - not needed now; tools/clone_model.py / clone_fit_check.py.
- Sonicake's MES conversion scored offline (tools/clone_score.py, held-out 20 s DI): calibration unknown, so
  scanned the NAM input scale c: best tone 2.2 dB at c~4 (ESR 0.33); at c = 6.3 (NAM input = DSP input sample)
  ESR 0.39, tone 3.3 dB.
- Buttons (key-map lists, msg = 2 | key<<8 | event<<16): keys 0, 1, 2 and 0x80, 0x81, 0x82; events 1, 3, 4, 5 on
  all of them (press / click / long / repeat [inferred]); event 6 only on key 2 in window 0x1FB30 (= double-push
  of the knob exists in the key driver). 0x81 event 3 only in the window entered at 0x22E80 (candidate ◁+▷).
- Windows registered @0x2C2E0.. (enter/exit/3rd callbacks), 16 windows; biggest key maps: enter 0x22E80 (99
  entries), 0x23674 (255). Lists in ui/windows.txt.
- CFW 1.0.2 already has a Settings section with Display -> Theme (Default, Amber CRT, Tube Amp, Synthwave, Stage
  HC, Game Boy), Light, ECO, and MIDI items (strings at file 0x116788 / 0x114CD0, CFW code area): brightness may
  already exist -> ask the user before building Phase 1.
- NDS32 GCC 13.2 (C) ready in docker image pmnds (/opt/nds/bin/nds32le-elf-gcc, libgcc installed).
- Capture-type detection (nam2clo.capture_type): tags are unreliable (#32868 full rig tagged "amp", 3 untagged).
  Feature that separates all 11 test captures: level drop 4 -> 8 kHz on guitar DI: amp-only -4.9..-10.5 dB,
  full rigs -16.2..-35.3 dB. Rule: < -15 full, > -11 amp, between: name words (cab, 4x12, full rig, mic names),
  then tag, then -13 dB.
- LVGL v8.3 compiled for NDS32 (ui/lvgl, -Os -mno-v3push -mno-ext-perf2) does not match the firmware's code
  shapes (5 of 3520 functions): GUI is not stock LVGL v8 (image/font formats are LVGL-like). Plan: own renderer
  for the new home/edit screens (scanline / small framebuffer, LCD routines @0x50B84/0x50B04), reusing only the
  window manager and key events.
- LCD flush = 0x50BE8 (x0, x1, y0, y1, pixels): window + one SPI burst of RGB565. GPIO 0x12224/0x12234 = pin
  set/clear (0x200 = LCD CS/DC), SPI write 0x6F93E. The stock GUI reaches the flush through a pointer; CFW 1.0.2
  hooks it (code ~0x16BD3C): theme byte @0x2001BB88 == 0 -> original flush, else the CFW recolours pixels
  first (themes). CFW code uses push25/pop25 (v3push) = same style as our GCC 13 -> compatible.
  The GUI renders through a 320-byte line buffer (malloc'd @0x149F8, gp-46200) -> scanline renderer.
  Plan for the new screens: own renderer that writes lines/tiles through 0x50BE8 while our windows are active.
- Edit page = window entered at 0x1A9B4 ("%s - %s" title @0x1C8FA); home screen code 0x23EFC..0x24E9C
  ("P%02d" @0x24A72, CPU "%d%%" @0x24174). Text helper 0x48CD0 (label printf), image set 0x479B8.
- Preset (11 4F) and clone (11 25) writes are refused while the pedal shows a Settings screen; they work from the home screen (2026-11-20).
- Display flush callback (LVGL-style flush_cb(disp, area{x1,y1,x2,y2 int16}, pixels)) = 0x4A9B4: calls the LCD
  flush 0x50BE8 (CFW: via trampoline 0x16BB60 -> theme hook 0x16BD3E) then j 0x43738 (= flush_ready). So the
  GUI *is* LVGL-like with a classic flush_cb -> try matching LVGL v7 (v8 did not match).
- CFW 1.0 user manual saved as re/cfw/cfw_manual.txt (settings meanings, MIDI, I/O, themes, ECO).
- Clone Treble knob = a shelf (2-6 kHz): Treble 0 -> -6 dB at 4 k, 50 -> -1 dB, 100 -> +4 dB. On top of it a FIXED
  steep low-pass inside the clone code: about -6 dB at 12 kHz, -30 dB at 16 kHz even at Treble 100 (likely an
  anti-aliasing / resampling filter). The gentle part is in the converter's model (fb can pre-compensate); the
  steep part above 12 kHz cannot be compensated sensibly.
- DI split changed: test = "Guitar R" take of every song, train = the other takes (all styles in both).
- Flash map (4 MB SPI flash; XIP: CPU = flash + 0x10000). Firmware sections: MCU app 0x000000-0x167F50, effect
  DB/presets 0x190000-0x1CD000, DSP kernel 0x200000, modules 0x240000, cab catalog 0x280000. Stock flash-access
  calls (0x10F62 / 0x11124 / 0x11482 / 0x514D4) use data areas at 0x180000, 0x18E000-0x18F000, 0x1D0000-0x1D1000,
  0x1E1000, 0x1F0100, 0x1F3000, 0x1FB000-0x1FD000, 0x1FF000 (settings, user IR/clone slots, ...). So the MCU gap
  is only 0x168000-0x17FFFF (96 KB) as code space, NOT 160 KB; 0x180000+ holds data. Still to check: where the
  CFW keeps its extra 5 IR + 5 clone slots, and how much of 0x168000-0x17FFFF is really never written.

## 51. Clone path in CFW 1.0.2 (for the own clone engine)
- The clone module (group 9) is byte-identical in stock V1.3.3 and CFW; the CFW kernel is 10 KB bigger.
- CFW manual: "IR after a Clone ... costs about 13 points on the DSP load meter" -> the CFW plays the selected
  IR on the ARM CPU after the engine block, not in the engine. So a replacement clone engine program does not
  break IR-after-clone, as long as the kernel's own handling stays. Engine layout for clones: code at word 0x500
  (state slot 0x28005400 + 9 KB), program ends with a jump to the EQ slot 0xE00 like the stock clone.
- Plan: one clone module = our amp code (3 stages, 2x) reading its settings from the slot data + an optional
  512-tap FIR stage (full rigs) with taps in the CAB block's engine data area (to verify free in clone mode).
- User IR upload (11 21) works (names change; NAK only when the payload was short - my bug). But playback test
  (2026-11-20 23:3x): User IR 5 = unit tap + 0.3 echo at 100 plays as one tap at -11 dB and no echo -> the IR
  block is not using the uploaded taps (cached at boot? CFW slot mapping?). User IR 1 (never uploaded) = silence.
  Next: power-cycle and re-test; check the CFW slot ids (10 slots).
- clone_probe.take: click search limited to the first 1.1 s; a late-started recording is padded instead of dropped.
- CORRECTION: the User IR "not playing our data" results (23:3x) were from a disconnected 3.5 mm jack (user, since
  ~23:14). With the jack back: User IR 5 = unit tap + echoes at 16/48/96/200/400 plays exactly (ratios 0.50/0.40/
  0.30/0.25/0.20, all 512 taps, ~3 samples delay). IR block gain at VOL 50: an int32 tap of 2^23 (= 1.0) gives
  about -12.2 dB. Upload format = CFW app's (cfw main.dart.js: 512 x int32 LE clamped +-8388607, 64-byte name).
- IR after OUR clone: no effect at all (echo-IR spectral test corr 0.02 vs 0.99 in Basic mode), both with the
  clone program ending at EQ (clone1) and at the CAB block (clone2). The CFW's IR-after-clone mechanism depends on
  something of the stock clone (not found yet: no literal jmp words / slot addresses in the CFW kernel).
  Stock cab module: e0 turns the int32 IR into a partitioned frequency-domain form in engine data 1408..3966
  (VOL at 3965/3966); engine program 467 words at code 2816.
- IR after a STOCK clone (dl14): plays exactly (comb test corr 0.99) and is a true convolution after the clone's
  own 512-tap filter (clone 2-tap at 300 + IR echo at 100 -> taps at 300, 100 and 400 = 0.5 x 0.4). Turning the
  IR on moves the main tap from 44 to 2 samples (latency drops by 42): the CFW changes the clone's output path.
- Our engine with the stock jump words kept at 1305/1684 (clone3): IR still not applied (corr 0.0) -> it is not a
  jump patch. Likely the CFW works on the stock clone's FIR-B stage / data. Not found statically yet.
- engine_emu cannot run the stock cab program (class 9 S6 '9d06'/'9346' unknown): cab path only verifiable on the pedal.
- OWN CLONE ENGINE WITH CAB WORKS (build/clone4 = dl14 + new clone module, flashed 2026-11-21 00:4x): our stub
  copies the pedal's own cab code (module image) to 0x10006400 at run time and calls its e0/e1 with int32 taps
  stored in the clone file; cab engine program placed at code 2816, amp program jumps there. Pedal: echo-cab comb
  test corr 0.99; cab stage gain -12.2 dB at 2^23 (compensated in nam2amp.make_clone via the amp output level).
  Pedal vs simulation vs capture: Super Reverb 0.000 / capture ESR 0.01, tone 0.72 dB, level +0.1 dB;
  MES 0.003 / capture ESR 0.10, tone 0.84 dB, level +0.4 dB. Co-processor ~122k units (amp + cab).
  Stub limits: 0x10003800-0x10003A00 (500 B used), run-time settings in .cdesc at 0x10006000 (not loaded).
- clone5 (own engine v2): amp core linked for 0x10003C00 inside the clone image; cab ARM code (0x10006400) and cab
  engine program (code 2816) copied at run time from the stock CAB blob; settings struct at 0x10006000.
  Cab choice = new 6th clone knob "Cab" (DB record patched): 0 = capture's own cab from the file, k = kernel cab
  index k-1 via the kernel's own lookup 0x6F0C (factory cabs 0..14, User IR n = 14+n). Pedal: User IR 5 via the
  knob plays exactly (comb corr 0.99), factory cab 1 plays, live switching works. The IR BLOCK itself must stay
  off in NAM presets: with our clone, IR block ON -> digital silence that persists (CFW IR-after-clone writes the
  cab area). UI must show the clone's Cab knob as the "IR" of a NAM and keep the real IR block off.
- 2026-11-21 03:3x: speed test ui3 (300 full frames + 2000 tiles + 64 KB malloc probe, run inside the flush hook
  = GUI task) left the pedal unresponsive (no USB audio/SysEx, then it dropped off USB). Recovered via the button
  combo (USB unplugged, combo, screen lit, then cable) + pmflash of clone5; P08 restored, audio OK.
  Likely cause: the GUI task blocked for minutes (and/or the big malloc). Next try: 30 frames + 300 tiles, 16 KB
  probe max. Never cancel a running reflash command.
- The updater refuses an MCU section of 0x17C1B4 bytes (ui3b, 2 test images): NAK 14 08 01 at the section-b header,
  twice; clone5 (0x167F50) flashes fine. So the MCU section has a size limit somewhere between 0x168056 (ui2, OK)
  and 0x17C1B4 - test images must be dropped; the real UI must find the exact limit (or keep its data elsewhere).
- MCU section size limit measured with tools/size_probe.py (clone5 + padding): +0x8000, +0x10000, +0x12000,
  +0x13000, +0x14000 (section 0x17BF50) all flash and boot; 0x17C1B4 is refused. Usable UI space = 0x17BF50 - 0x168000
  = 79.8 KB (not 96 KB). Pedal restored to clone5, P08 restored, audio OK (-31 dB).
- SPEED TEST RESULT (ui3d, user stopwatch, 2026-11-21): 300 full-screen redraws (8 strips of 160x16, pattern computed
  per pixel in C) = about 1 s -> ~3 ms per full frame incl. our own per-pixel maths; 3000 tile pushes (32x48,
  per-pixel computed) = about 3.5 s -> ~1.2 ms per 32x48 tile. => the LCD path is fast; animations are cheap.
  Memory probe: a 16 KB malloc succeeds (CYAN) after boot with our 5 KB strip buffer already taken => free heap
  >= 16 KB (32 KB probe not tried in the final version). The test then left the pedal not answering USB: most
  likely the leaked probe block exhausted the heap for the GUI/USB tasks (never leak; free probes). Design rule:
  strip buffer 160x8 (2.5 KB), total UI heap < 8 KB, allocate once at start, never in the draw loop.
