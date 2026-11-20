#!/usr/bin/env python3
"""Our reverb engine into RVB slots: build_rv.py <base build dir> <out name>
Engine code (dsp/reverb.c + rv_voices.c + rv_entries.c) runs in place from module-image space left free by the amp
build (<base>/free_after.json), split over two runs; each target RVB slot gets a 24-byte thunk header pointing at
its entry pair. Titles changed by cloning the DB record (same knobs) into the DB padding."""
import os, shutil, struct, subprocess, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
from build_cut import groups
from build_bisect import zero_run
DSP = os.path.join(RE, "dsp")
SLOTS = {1: (0, None), 0: (1, "Chamber"), 2: (2, None), 3: (3, None), 4: (4, "Plate"), 5: (5, "Shimmer"),
         6: (6, None), 9: (7, None), 11: (8, None)}            # RVB index -> (voice, new title)
FLAGS = ("-mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16 -O2 -ffreestanding -nostdlib -fno-builtin "
         "-ffunction-sections -fdata-sections -fsingle-precision-constant -Wall -Wno-misleading-indentation")


def clone_title(d, rec_off, title):
    """copy the DB record at rec_off with a new title (strings re-laid, knob name offsets shifted)"""
    n = d[rec_off + 8]; sb = rec_off + 16 + 24 * n
    old = d[sb:d.find(b"\0", sb)]; i = sb; end = sb
    for _ in range(2 + n): end = d.find(b"\0", end) + 1                      # title, category, names
    strings = bytes(d[sb:end]); new_s = title.encode() + b"\0" + strings[len(old) + 1:]; shift = len(new_s) - len(strings)
    rec = bytearray(d[rec_off:sb]); cat = struct.unpack_from("<H", rec, 14)[0]; struct.pack_into("<H", rec, 14, cat + shift)
    for k in range(n): o = 16 + 24 * k + 2; struct.pack_into("<H", rec, o, struct.unpack_from("<H", rec, o)[0] + shift)
    return bytes(rec) + new_s


def main():
    base, name = sys.argv[1], sys.argv[2]
    out = os.path.join(RE, "build", name); src = os.path.join(out, "src"); shutil.rmtree(src, ignore_errors=True)
    shutil.copytree(os.path.join(base, "src"), src)
    mp = os.path.join(src, "1_dsp_modules_00240000.bin"); m = bytearray(open(mp, "rb").read())
    dp = os.path.join(src, "4_effect_db_presets_00190000.bin"); d = bytearray(open(dp, "rb").read())
    free = [tuple(x) for x in json.load(open(os.path.join(base, "free_after.json")))]
    (oa, la), (ob, lb) = free[0], free[1]; hdr_run = free[2]
    open(os.path.join(DSP, "link-rv.ld"), "w").write(
        f"ENTRY(rv0_e1)\nMEMORY {{ A (rx) : ORIGIN = 0x{0x13000 + oa:X}, LENGTH = {la}\n         B (rx) : ORIGIN = 0x{0x13000 + ob:X}, LENGTH = {lb} }}\n"
        "SECTIONS {\n  .ta : { /tmp/reverb.o(.text* .rodata*) } > A\n"
        "  .tb : { KEEP(*(.text.rv*_e0)) KEEP(*(.text.rv*_e1)) *(.text*) *(.rodata*) } > B\n  .data : { *(.data*) *(.bss*) *(COMMON) } > B\n"
        "  /DISCARD/ : { *(.ARM.*) *(.comment) }\n}\nASSERT(SIZEOF(.data) == 0, \"no RAM data allowed (in-place code)\");\n")
    sh = (f'set -e; F="{FLAGS}"; for f in pmfx reverb rv_voices rv_entries; do arm-none-eabi-gcc $F -c $f.c -o /tmp/$f.o; done; '
          'arm-none-eabi-gcc $F -T link-rv.ld -Wl,--gc-sections -nostartfiles /tmp/pmfx.o /tmp/reverb.o /tmp/rv_voices.o /tmp/rv_entries.o -o rv.elf -lgcc; '
          'arm-none-eabi-objcopy -O binary -j .ta rv.elf rv_a.bin; arm-none-eabi-objcopy -O binary -j .tb rv.elf rv_b.bin; arm-none-eabi-nm rv.elf > rv.sym')
    subprocess.run(["sh", "-c", "sync; sleep 2"], check=True)
    subprocess.run(["docker", "run", "--rm", "-v", f"{DSP}:/w", "-w", "/w", "pmarm", "sh", "-c", sh], check=True)
    for f, o, ln in (("rv_a.bin", oa, la), ("rv_b.bin", ob, lb)):
        b = open(os.path.join(DSP, f), "rb").read(); assert len(b) <= ln, (f, len(b), ln)          # space of retired amps (old bytes, unused)
        m[o:o + len(b)] = b
    sym = {l.split()[2]: int(l.split()[0], 16) for l in open(os.path.join(DSP, "rv.sym")) if len(l.split()) == 3}
    gm, gd = groups(m, 0), groups(d, 0x10000); lp = struct.unpack_from("<I", m, 0x14 + 4 * 8)[0]
    dlp = struct.unpack_from("<I", d, 0x10000 + 0x14 + 4 * 8)[0]; ho, hl = hdr_run; log = []
    for slot, (vi, title) in SLOTS.items():
        h = struct.pack("<6I", 0x18, 0, 0x18, 0, sym[f"rv{vi}_e0"] | 1, sym[f"rv{vi}_e1"] | 1)
        assert hl >= 32; m[ho:ho + 24] = h; struct.pack_into("<I", m, lp + 4 + 4 * slot, ho)
        ho += 32; hl -= 32
        if title:
            rec = clone_title(d, 0x10000 + gd[8][slot], title); z = zero_run(d, 0x10000, len(rec) + 64, 0x20000); at = (z + 16) & ~3
            d[at:at + len(rec)] = rec; struct.pack_into("<I", d, 0x10000 + dlp + 4 + 4 * slot, at - 0x10000)
        log.append(f"RVB {slot} -> voice {vi}{' ' + title if title else ''}")
    open(mp, "wb").write(m); open(dp, "wb").write(d)
    json.dump([list(x) for x in free[3:]] + [[ho, hl]], open(os.path.join(out, "free_after.json"), "w"))
    binf = os.path.join(out, f"PocketMaster_CFW1.0.2+{name}.bin")
    subprocess.run([sys.executable, os.path.join(RE, "pmfw.py"), "pack", src, binf], check=True, stdout=subprocess.DEVNULL)
    print(f"engine: {os.path.getsize(os.path.join(DSP, 'rv_a.bin'))} + {os.path.getsize(os.path.join(DSP, 'rv_b.bin'))} bytes in place"); print("\n".join(log)); print("built", os.path.relpath(binf, RE))


if __name__ == "__main__":
    main()
