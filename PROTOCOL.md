# Pocket Master USB-MIDI SysEx protocol (from Sonicake Manager 1.5.2 captures)

Status: framing, checksum, presets, IR/clone upload and firmware update are **[confirmed]** against captures. Every captured frame passes the CRC (≈220,000 frames), and the firmware stream rebuilds the `.bin` sections byte-for-byte. Field meanings marked *(?)* are guesses.
Tools: `tools/mmon2txt.py` (MIDI Monitor → text), `tools/pmsysex.py` (decode/encode).

## 1. Framing

```
wire:    F0  n n n n n n ...  F7        every logical byte is sent as 2 bytes: high nibble, low nibble (0x00–0x0F)
logical: crc8 | count | index | length | payload[length]
```
- `crc8`: CRC-8, poly 0x07, init 0, no reflection, no final XOR, over `count|index|length|payload`.
- `count` = frames in this message (1–254), `index` = 0…count-1. The app sends at most 19 payload bytes per frame.
- **Bulk stream** (firmware): `count = 0xFF`, `index` wraps 0…255.
- A message = the concatenated payloads. Its first 2 bytes are the **command** `<class> <object>`:
  - `0x11` = write/set (Mac→pedal; also the reply to the handshake)
  - `0x12` = read/get (request, and the reply echoes it)
  - `0x14 0x08 <code>` = per-frame ACK from the pedal (`00` = OK, `01` = busy/rejected *(?)*)
- The app also sends MIDI clock `F8` about every 3 s (keep-alive or tempo *(?)*).

## 2. Commands seen

| Cmd | Dir | Data | Meaning |
|---|---|---|---|
| `12 30` → `11 30` | ⇄ | reply `01 00` (normal app) / `01 01` (update mode) | handshake; byte 1 = running mode |
| `12 10` | ⇄ | reply 69 B TLV (§3) | device info |
| `12 40` | ⇄ | reply 2000 B = 100 × {u32 index, char name[16]} | preset name list |
| `12 4F` | ⇄ | req `u32 index`; reply 494 B preset (§4) | read preset |
| `11 4F` | > | 494 B preset with `u32 index` in place of `FFFFFFFF` | write preset |
| `11 4C` | > | `u32 index` + name (NUL-padded) | rename preset |
| `12 20` | ⇄ | reply 85 B: `u8 empty[5]` + 5 × `char[16]` | user IR slot list (`empty`: 1 = empty) |
| `11 21` | > | 2120 B IR upload (§5) | write user IR |
| `12 24` | ⇄ | reply 85 B, same layout | clone slot list |
| `11 25` | > | 2768 B clone upload (§6) | write clone |
| `12 1B` | < | `u32 event` | change notice. Seen: 1 = current preset changed, 2 = preset data changed, 3 = clone list changed, 4 = IR list changed *(?)* |
| `12 43` | < | `u32 preset index` | current preset (sent when you change preset on the pedal) |
| `11 6F 60 61 69 6E` | > | see §7 | firmware update |

## 3. Device info (`12 10`): TLV list of `{u16 tag, u16 len, value}`

`0x0101` = `03 03 01 01` (version *(?)*), `0x0102` = 2, `0x0202` = 23, `0x0201` = 1, **`0x0203` = 100 (preset count)**, `0x0301`, `0x0401`–`0x0405`, `0x0205`: small flags *(?)*.

## 4. Preset (494 bytes)
```
u32 index (FFFFFFFF in read replies) | char name[16] | TLV tree:
 00FF { 0001 { 0002 {} }, 0002: "\x0aEMQ" (u32 'QME' + 10 → device model QME-10?) }
 0000 { 1001: 10 (modules), 1002: 8 (params per module), 1003: 2 }
 0001 { 2001: 65 (preset volume?), 2002: 120 (BPM?) }
 0002 { 3001: u32 enable bitmask (bit n = module n on)
        3002: u8 order[10] (signal-chain order, 0..9)
        3003: u32 fxid[10]   (which effect per module; same IDs as the app's *_module_data.json and the firmware effect DB)
        3004: f32 param[10][8] (values in UI units, e.g. Gain 0–100, delay time ms) }
 0003 { 0000 {}, 0000 {} }
```
Module order and fxid top byte: 0 NR (`0x0000001B` Gate), 1 FX1 (`0x00..`), 2 DRV (`0x03..`), 3 AMP (`0x07..`), 4 IR (`0x0A..`), 5 EQ (`0x01..`), 6 FX2 (`0x04..`), 7 DLY (`0x0B..`), 8 RVB (`0x0C..`), 9 Clone (`0x0F..`).

## 5. User IR upload (`11 21`, 2120 bytes)
```
u32 0 | u32 slot_id = 0x0A100000 + slot(0..4) | char name[16] | 48 × 0 | int32 ir[512]
```
The IR is **512 taps** (≈ 11.6 ms at 44.1 kHz), stored as signed 32-bit values that peak around 2^23, so probably 24-bit fixed-point *(?)*. The app converts and truncates the user's WAV.

## 6. Clone upload (`11 25`, 2768 bytes) and the `.clo` format
```
u32 0 | u32 slot_id = 0x0F000000 + slot(0..4) | char name[16] | 48 × 0 | device .clo (2696 B)
```
`.clo` ("VTSI" file; the desktop cache copy is 8840 B, the device copy 2696 B):

| Off | Field |
|---|---|
| 0x00 | `"VTSI"` |
| 0x04 | u32 total size |
| 0x08 | u32 checksum = CRC-16/MODBUS over bytes 0x0C…end, stored byte-swapped **[confirmed on both files]** |
| 0x14 | u32 data size (0x2200 desktop / 0xA00 device) |
| 0x18 | f64[5] biquad A = {1,0,0,0,0} (identity) |
| 0x40 | f64[5] biquad B = {0.9963, -1.9926, 0.9963, -1.9926, 0.9926} (2nd-order high-pass, ~25 Hz DC blocker) |
| 0x68 | f32[4] {0.0616, 0.0606, 546.27, 624.13} (gains / nonlinearity parameters *(?)*) |
| 0x78 | u32[4] {0, 128, 128, N}: offsets/lengths of two arrays (N = 2048 desktop, 512 device) |
| 0x88 | f32[128] filter A, then f32[N] filter/IR B |

So a "clone" is a **filter → (parametric nonlinearity?) → 128-tap FIR → 512-tap IR** model. That is far cheaper than NAM, and it explains how a NAM A2 file becomes a ~2.7 KB clone. The device copy is the desktop copy with IR B cut from 2048 to 512 taps.

## 7. Firmware update (re-flash of V1.3.3, ~4.5 min)
```
> 11 6F                         enter update mode (pedal reboots into updater; handshake then replies 01 01)
> 12 30 / < 11 30 01 01         ×2
> 11 69 "V133\0"                ×10 (version announce; pedal ACKs with 01)
> 11 60                         start
per section, in file order:
> 11 61 {u32 type, u32 frames, u32 bytes}   bytes = section size + 2, frames = ceil(bytes/19)
> stream (count=0xFF): 11 <type> + raw section bytes     ← byte-identical to the .bin section, no encryption
> 11 6E <type>                  section done
> 11 6E 'n'(0x6E)              all done → reboot; handshake replies 01 00 again
```
- **No CRC, signature or HTFW header is sent.** The header word @0x04 and the section CRC-16s are only checked by the app (`checkCrc`, `isRealFirmware`), if at all. The pedal is never sent them.
- Every frame is ACKed (`14 08 00`). 11 frames got `01` during the version announce.
- It is not known whether the pedal checks anything itself.
