#!/usr/bin/env python3
"""Our amps into AMP slots: build_amps.py <base build dir> <out name> <slot>=<fit json>[:<new name>] ...
The blob (header + amp_one ARM code + amps2 engine program) goes into the slot's own blob space when that is a real
blob (Bog XT), never past its own size. Knob mapping from the stock record's knob names."""
import os, shutil, struct, subprocess, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import amps2, amp_capture as AC
from build_cut import groups
DSP = os.path.join(RE, "dsp")
OURS = ["Gain", "Bass", "Middle", "Treble", "PRES", "VOL", "Bright"]
FLAGS = ("-mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16 -Os -ffreestanding -nostdlib -fno-builtin "
         "-ffunction-sections -fdata-sections -fsingle-precision-constant -Wall -Wno-unused-function")


def compile_amp(fit, knob_index):
    amps2.export(fit, knob_index)
    sh = (f'set -e; F="{FLAGS}"; arm-none-eabi-gcc $F -c pmfx.c -o /tmp/p.o; arm-none-eabi-gcc $F -c amp.c -o /tmp/a.o; '
          f'arm-none-eabi-gcc $F -c amp_one.c -o /tmp/o.o; arm-none-eabi-gcc $F -T link-amp.ld -Wl,--gc-sections -nostartfiles '
          f'/tmp/p.o /tmp/a.o /tmp/o.o -o amp_one.elf -lgcc; arm-none-eabi-objcopy -O binary -j .text amp_one.elf amp_one.bin; arm-none-eabi-nm amp_one.elf > amp_one.sym')
    subprocess.run(["sh", "-c", "sync; sleep 2"], check=True)
    subprocess.run(["docker", "run", "--rm", "-v", f"{DSP}:/w", "-w", "/w", "pmarm", "sh", "-c", sh], check=True)
    code = open(os.path.join(DSP, "amp_one.bin"), "rb").read(); code += b"\0" * ((-len(code)) % 4)
    sym = {l.split()[2]: int(l.split()[0], 16) for l in open(os.path.join(DSP, "amp_one.sym")) if len(l.split()) == 3}
    return code, sym["amp_entry0"] | 1, sym["amp_entry1"] | 1


def main():
    base, name, jobs = sys.argv[1], sys.argv[2], sys.argv[3:]
    out = os.path.join(RE, "build", name); src = os.path.join(out, "src"); shutil.rmtree(src, ignore_errors=True)
    shutil.copytree(os.path.join(base, "src"), src)
    mp = os.path.join(src, "1_dsp_modules_00240000.bin"); m = bytearray(open(mp, "rb").read())
    dp = os.path.join(src, "4_effect_db_presets_00190000.bin"); d = bytearray(open(dp, "rb").read())
    n0m, n0d = len(m), len(d); gm, gd = groups(m, 0), groups(d, 0x10000); stock = AC.stock_amps()
    names = {struct.unpack_from("<I", d, 0x10000 + r)[0]: i for i, r in enumerate(gd[3])}
    for j in jobs:
        slot, rest = j.split("="); slot = int(slot); fit, _, newname = rest.partition(":")
        r = 0x10000 + gd[3][slot]; nxt = 0x10000 + min(x for gl in gd for x in gl if x > gd[3][slot])
        stock_name = next(k for k, v in stock.items() if v[0] == struct.unpack_from("<I", d, r)[0]); kn = stock[stock_name][1]
        alias = {"Tone": "Treble", "Presence": "PRES"}
        idx = [next((i for i, k in enumerate(kn) if alias.get(k, k) == o), -1) for o in OURS]
        s = json.load(open(fit)); prog, _ = amps2.assemble_amp(int(s["nst"]), int(s.get("os", 4))); prog = np.array(prog, "<u4").tobytes()
        code, e0, e1 = compile_amp(fit, idx)
        o = gm[3][slot]; hs, cs, ts, st = struct.unpack_from("<4I", m, o); own = ts + st
        assert cs > 0, f"slot {slot} is a thunk; use a real blob slot"
        hdr = bytearray(m[o:o + hs]); struct.pack_into("<5I", hdr, 4, len(code), hs + len(code), len(prog), e0, e1)
        blob = bytes(hdr) + code + prog; assert len(blob) <= own, (len(blob), own)
        m[o:o + own] = blob + b"\0" * (own - len(blob))
        if newname:
            j0 = d.find(stock_name.encode() + b"\0", r, nxt); nb = newname.encode()[:len(stock_name)].ljust(len(stock_name))
            d[j0:j0 + len(nb)] = nb
        print(f"AMP {slot} ({stock_name}) -> {os.path.basename(fit)} '{newname}': {len(blob)} of {own} bytes, knobs {idx}")
    assert len(m) == n0m and len(d) == n0d and groups(m, 0) == gm and groups(d, 0x10000) == gd
    open(mp, "wb").write(m); open(dp, "wb").write(d)
    binf = os.path.join(out, f"PocketMaster_CFW1.0.2+{name}.bin")
    subprocess.run([sys.executable, os.path.join(RE, "pmfw.py"), "pack", src, binf], check=True, stdout=subprocess.DEVNULL)
    print("built", os.path.relpath(binf, RE))


if __name__ == "__main__":
    main()
