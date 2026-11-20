#!/usr/bin/env python3
"""Our CPU-side effects into FX slots (own blob space only): build_fx.py <base build dir> <out name> <group>:<index>=<src.c>[:<defines>] ...
group 6 = FX2 (linked at 0x10009000, dsp/link-fx2.ld)."""
import os, shutil, struct, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
from build_cut import groups
DSP = os.path.join(RE, "dsp"); LD = {6: "link-fx2.ld"}
FLAGS = ("-mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16 -Os -ffreestanding -nostdlib -fno-builtin "
         "-ffunction-sections -fdata-sections -fsingle-precision-constant -Wall -Wno-unused-function -Wno-unused-variable")


def compile_fx(src, defs, ld, tag):
    D = " ".join(f"-D{x}" for x in defs if x)
    sh = (f'set -e; F="{FLAGS} {D}"; arm-none-eabi-gcc $F -c pmfx.c -o /tmp/p.o; arm-none-eabi-gcc $F -c {src} -o /tmp/x.o; '
          f'arm-none-eabi-gcc $F -T {ld} -Wl,--gc-sections -nostartfiles /tmp/p.o /tmp/x.o -o fx_{tag}.elf -lgcc; '
          f'arm-none-eabi-objcopy -O binary fx_{tag}.elf fx_{tag}.bin; arm-none-eabi-nm fx_{tag}.elf > fx_{tag}.sym')
    subprocess.run(["sh", "-c", "sync; sleep 2"], check=True)
    subprocess.run(["docker", "run", "--rm", "-v", f"{DSP}:/w", "-w", "/w", "pmarm", "sh", "-c", sh], check=True)
    code = open(os.path.join(DSP, f"fx_{tag}.bin"), "rb").read(); code += b"\0" * ((-len(code)) % 4)
    sym = {l.split()[2]: int(l.split()[0], 16) for l in open(os.path.join(DSP, f"fx_{tag}.sym")) if len(l.split()) == 3}
    return code, sym["lt_entry0"] | 1, sym["lt_entry1"] | 1


def main():
    base, name, jobs = sys.argv[1], sys.argv[2], sys.argv[3:]
    out = os.path.join(RE, "build", name); src = os.path.join(out, "src"); shutil.rmtree(src, ignore_errors=True)
    shutil.copytree(os.path.join(base, "src"), src)
    mp = os.path.join(src, "1_dsp_modules_00240000.bin"); m = bytearray(open(mp, "rb").read()); n0 = len(m); g = groups(m, 0)
    for j in jobs:
        slot, rest = j.split("="); grp, idx = map(int, slot.split(":")); f, _, defs = rest.partition(":")
        o = g[grp][idx]; hs, cs, ts, st = struct.unpack_from("<4I", m, o); own = ts + st; assert cs > 0
        code, e0, e1 = compile_fx(f, defs.split(","), LD[grp], f"{grp}_{idx}")
        hdr = bytearray(m[o:o + hs]); struct.pack_into("<5I", hdr, 4, len(code), hs + len(code), 0, e0, e1)
        blob = bytes(hdr) + code; assert len(blob) <= own, (len(blob), own)
        m[o:o + own] = blob + b"\0" * (own - len(blob)); print(f"group {grp} #{idx}: {f} {defs} {len(blob)} of {own} bytes")
    assert len(m) == n0 and groups(m, 0) == g
    open(mp, "wb").write(m)
    binf = os.path.join(out, f"PocketMaster_CFW1.0.2+{name}.bin")
    subprocess.run([sys.executable, os.path.join(RE, "pmfw.py"), "pack", src, binf], check=True, stdout=subprocess.DEVNULL)
    print("built", os.path.relpath(binf, RE))


if __name__ == "__main__":
    main()
