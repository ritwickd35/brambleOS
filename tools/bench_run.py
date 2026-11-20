#!/usr/bin/env python3
"""Cut 3 step 1 (firmware cut3a, 'Bench Test' in DRV): run and decode.

  bench_run.py run              write P08 = DRV 'Bench Test' only, select it, play 1 kHz, record 125 s, decode,
                                restore P08 byte-identically
  bench_run.py decode <wav>     decode a recording

Firmware cut3b ('CPU Test 2' in DRV, Treble = 0 -> probe mode): sends 24 + 2 values as deliberate dropouts
(per value 22 slots of 0.125 s = 1 1 1 0 + 16 bits MSB first + 0 0), then mutes the first n floats of entry1's
first argument for 1 s every 2 s (6 times) if that pointer looks like audio.
"""
import os, struct, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pmloadtest as L
FS = 44100; SLOT = 86 * 64 / FS          # 0.12481 s
NAMES = ["magic", "CPUID hi", "CPUID lo", "ID_ISAR3", "n", "arg0 hi", "arg0 lo", "arg2 hi", "arg2 lo",
         "arg3 hi", "arg3 lo", "arg4 hi", "arg4 lo", "arg5 hi", "arg5 lo", "arg6 hi", "arg6 lo",
         "peak |arg0| x1e4", "peak |arg3| x1e4", "block period / 16", "overhead", "float 1024 MAC (internal RAM)",
         "64 x rational tanh", "biquad 64 samples", "float 1024 MAC (weights in SDRAM)", "int16 1024 MAC (SMLAD)"]


def dropouts(y):
    return [t for t, _ in L.glitches(y)]


def dips(y, w=8):
    """Start times of every short dip (8-sample window below 30 % of the median level), not merged."""
    n = len(y) // w; e = np.sqrt(np.mean(y[:n * w].reshape(n, w) ** 2, 1)); med = np.median(e)
    low = np.where(e < 0.3 * med)[0]
    if not len(low): return np.array([])
    keep = np.concatenate([[True], np.diff(low) > 2])
    return low[keep] * w / FS


def _grid(g, start, frames):
    """Read `frames` values on a fixed slot grid from `start` (time of the first dip of the first preamble)."""
    out = []
    for k in range(frames):
        bits = []
        for sl in range(22):
            b = start + (22 * k + sl) * SLOT
            bits.append(int(np.sum((g >= b + 0.02) & (g <= b + SLOT - 0.005)) >= 2))
        ok = bits[:4] == [1, 1, 1, 0] and bits[20:] == [0, 0]
        v = int("".join(map(str, bits[4:20])), 2)
        out.append((round(float(start + 22 * k * SLOT), 2), v if ok else None))
    return out


def decode(path, t_from=7.5):
    """Report bits are dips (zeroed audio) spread over a whole 0.125 s slot (cut3d)."""
    y = L.load(path); g = dips(y)
    print(f"{os.path.basename(path)}: {len(g)} dips")
    g1 = g[g > t_from]
    if not len(g1): return y, []
    s1 = g1[0] - 0.003
    res = _grid(g, s1, 24)
    end1 = s1 + 24 * 22 * SLOT
    g2 = g[g > end1 + 0.05]
    if len(g2): res += _grid(g, g2[0] - 0.003, 2)
    return y, [(t, v if v is not None else -1) for t, v in res]


def audio_test(y, t_sel):
    """Level per 0.5 s from 0 to 16 s after the preset selection (muted half-blocks show as lower level)."""
    w = int(0.25 * FS); out = []
    for k in range(64):
        s = y[int((t_sel + k * 0.25) * FS):int((t_sel + k * 0.25) * FS) + w]
        out.append(round(float(20 * np.log10(np.std(s) + 1e-9)), 1))
    return out


def report(path, t_sel=None):
    y, res = decode(path)
    for k, (t, v) in enumerate(res):
        print(f"  {t:7.2f} s  value {k:2d} {NAMES[k]:34s} = {v:5d}  (0x{v:04X})")
    if len(res) >= 24 and res[0][1] == 0xA55A:
        v = [x if x >= 0 else None for _, x in res] + [None] * (26 - len(res))
        cpuid = v[1] << 16 | v[2]; part = (cpuid >> 4) & 0xFFF
        core = {0xC24: "Cortex-M4", 0xC27: "Cortex-M7", 0xD21: "Cortex-M33", 0xC23: "Cortex-M3"}.get(part, hex(part))
        print(f"  CPU: CPUID 0x{cpuid:08X} = {core} r{(cpuid >> 20) & 0xF}p{cpuid & 0xF}; ID_ISAR3 SIMD = {(v[3] >> 4) & 0xF} (3 = DSP extension)")
        args = {f"arg{i}": v[j] << 16 | v[j + 1] for i, j in ((0, 5), (2, 7), (3, 9), (4, 11), (5, 13), (6, 15))}
        print("  entry1 args:", ", ".join(f"{k}=0x{x:08X}" for k, x in args.items()), f"n={v[4]}")
        print(f"  peak |arg0[0..n)| = {v[17] / 1e4 if v[17] < 0xFFFD else 'n/a'}, peak |arg3[0..n)| = {v[18] / 1e4 if v[18] < 0xFFFD else 'n/a'}")
        print(f"  SysTick: block period {v[19] * 16} ticks -> {v[19] * 16 / (64 / FS) / 1e6:.1f} MHz")
        ov = v[20]
        for i, per, label in ((21, 1024, "float MAC, internal RAM"), (22, 64, "rational tanh (1 divide)"),
                              (23, 64, "biquad sample (5 MACs)"), (24, 1024, "float MAC, weights in SDRAM"),
                              (25, 1024, "int16 MAC (SMLAD)")):
            if v[i] is None: print(f"  {label:32s} not received"); continue
            if v[i] == 0xFFFF: print(f"  {label:32s} skipped"); continue
            print(f"  {label:32s} {v[i]:5d} ticks -> {max(v[i] - ov, 1) / per:.2f} cycles each")
    if t_sel is not None and len(res) >= 26:
        t_audio = res[25][0] + 22 * SLOT
        print("  audio test (level every 0.25 s, mute phases at 0-1, 2-3, ... s):", audio_test(y, t_audio))


def run():
    import sounddevice as sd, pmaudio
    from pmflash import Link
    from cut1_variants import read_p, describe
    from cut1_matrix import send, set_mod, get_mod
    link = Link(); orig = read_p(link); link.close()
    fx, prm = get_mod(orig, 2)
    rec = orig
    for m in range(10): rec = set_mod(rec, m, on=False)
    prm = list(prm); prm[4] = 0.0                       # Treble = 0 -> probe mode
    rec = set_mod(rec, 2, fx, prm, True)
    print("test preset: on =", describe(rec), " DRV fx", hex(fx))
    os.makedirs(L.OUT, exist_ok=True)
    path = os.path.join(L.OUT, time.strftime("%Y%m%d-%H%M%S") + "-bench.wav")
    secs = 110
    t = np.arange(int(FS * (secs + 3))) / FS; tone = (0.1 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
    p = pmaudio.record(path, secs); time.sleep(2.0)
    t_play = time.time()
    sd.play(np.stack([tone, tone], 1), samplerate=FS, device=pmaudio.out_device("External Headphones"))
    time.sleep(4.0)
    send(rec); t_sel_wall = time.time()
    print("selected; recording ...", flush=True)
    p.wait(); sd.stop()
    send(orig); time.sleep(0.5)
    link = Link(); back = read_p(link); link.close()
    print("P08 restored:", "OK (byte-identical)" if back[4:] == orig[4:] else "MISMATCH")
    # selection time inside the recording: the first dropout after 4 s of tone
    y = L.load(path); g = dropouts(y)
    t_sel = next((x for x in g if x > 3.0), None)
    print("saved", path, "| preset switch dropout at", t_sel)
    report(path, t_sel)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["run"]: run()
    elif len(a) == 2 and a[0] == "decode": report(a[1])
    else: sys.exit(__doc__)
