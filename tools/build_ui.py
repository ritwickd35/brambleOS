#!/usr/bin/env python3
"""UI builds: base build dir + our C code placed at flash 0x168000 (CPU 0x178000, 96 KB free) + the theme-hook patch.
  build_ui.py <base build dir> <out name> <ui source dir>      (source dir: *.c, link.ld; entry = ui_hook first in .text)
The call at 0x16BD54 (CFW theme hook: movi r5,#0x50be8; jral5 r5) is replaced by `jal ui_hook; nop16`."""
import glob, os, shutil, struct, subprocess, sys
RE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GCC = "/out/bin/nds32le-elf-"; BIN = "/opt/nds/bin/nds32le-elf-"      # compiler: ui/nds (built by ui/build_gcc.sh), binutils in pmre


def main():
    base, name, srcdir = sys.argv[1:4]; srcdir = os.path.abspath(srcdir)
    subprocess.run(["docker", "run", "--rm", "-v", f"{srcdir}:/w", "-v", f"{os.path.join(RE, 'ui', 'nds')}:/out", "-w", "/w", "pmre", "sh", "-c",
        f"export PATH=/opt/nds/bin:$PATH; for f in *.c; do {GCC}gcc -Os -ffreestanding -fno-builtin -nostdlib -c $f -o ${{f%.c}}.o || exit 1; done; "
        f"{BIN}ld -T link.ld *.o -o ui.elf && {BIN}objcopy -O binary ui.elf ui.bin && {BIN}nm ui.elf > ui.sym"], check=True)
    code = open(os.path.join(srcdir, "ui.bin"), "rb").read(); sym = {l.split()[2]: int(l.split()[0], 16) for l in open(os.path.join(srcdir, "ui.sym")) if len(l.split()) == 3}
    out = os.path.join(RE, "build", name); shutil.rmtree(out, ignore_errors=True); shutil.copytree(os.path.join(RE, base) if not os.path.isabs(base) else base, out)
    p = os.path.join(out, "src", "3_mcu_app_00000000.bin"); b = bytearray(open(p, "rb").read())
    assert len(b) <= 0x168000 and len(code) <= 0x18000, (hex(len(b)), len(code))
    o = 0x16BD54 - 0x10000; assert b[o:o + 6] == bytes.fromhex("44550be8dd25"), b[o:o + 6].hex()
    b += b"\xff" * (0x168000 - len(b)); b += code
    b[o:o + 4] = struct.pack(">I", 0x49000000 | (((sym["ui_hook"] - 0x16BD54) // 2) & 0xFFFFFF)); b[o + 4:o + 6] = bytes.fromhex("9200")
    open(p, "wb").write(b)
    binf = os.path.join(out, f"PocketMaster_CFW1.0.2+{name}.bin")
    subprocess.run([sys.executable, os.path.join(RE, "pmfw.py"), "pack", os.path.join(out, "src"), binf], check=True, stdout=subprocess.DEVNULL)
    print(f"{name}: UI code {len(code)} bytes at CPU 0x178000 (hook {sym['ui_hook']:#x}), MCU section {len(b):#x}; {os.path.relpath(binf, RE)}")


if __name__ == "__main__":
    main()
