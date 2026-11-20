#!/usr/bin/env python3
"""Cut 4a probe (FX1 'CPUTest' on CFW 1.0.2 + tests): run and decode.

  fx1probe_run.py run            P08 = only FX1 'CPUTest' (Depth 0), select, arm the risky tests with a live,
                                 unsaved edit Depth = 1 after 3.5 s, record 75 s, restore P08 byte-identically
  fx1probe_run.py decode <wav>   decode a recording
"""
import os, struct, sys, time, wave
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
FS = 44100; SLOT = 86 * 64 / FS; BPS = 689 * 64 / FS
FXID = 0x05000008                 # FX1 #15 slot of the CFW ('C-Wah', replaced by the probe in cut4b)
NAMES = ["magic", "n (frames per block)", "buf hi", "buf lo", "block period / 16", "overhead",
         "dot 1024 MAC, code in slot RAM", "dot 1024 MAC, code on stack", "dot 1024 MAC, code in module image",
         "dot 1024 MAC, slot code + data on stack", "A2 layer float, 32 samples", "A2 layer int16 SMLAD, 32 samples",
         "flags", "peak |buf| x1e4", "image code addr hi", "image code addr lo"]


def load2(path):
    with wave.open(path) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32).reshape(-1, 2) / 32768


def env(x, w=64):
    n = len(x) // w; return np.sqrt(np.mean(x[:n * w].reshape(n, w) ** 2, 1))


def decode(path):
    y = load2(path); m = 0.5 * (y[:, 0] + y[:, 1]); e = env(m); med = np.median(e[e > 0]) if np.any(e > 0) else 0
    low = e < 0.1 * med; tw = 64 / FS
    # find the first preamble: three muted slots in a row after the audio test
    frac = lambda t0: float(np.mean(low[int(t0 / tw):int((t0 + SLOT) / tw)]))
    i = int(8.0 / tw); start = None; iend = int((len(m) / FS - 25 * SLOT) / tw)
    while i < min(iend, len(low)):
        if low[i]:
            # candidate: run of low windows lasting ~3 slots (integer indices: no float drift, always advances)
            j = i
            while j < len(low) and low[j]: j += 1
            if abs((j - i) * tw - 3 * SLOT) < 0.06: start = i * tw; break
            i = j
        else:
            i += 1
    vals = []
    if start is None: return y, None, vals
    base = start
    for k in range(len(NAMES)):
        # re-synchronise on each frame's preamble (3 muted slots): the pedal skips the module in some blocks,
        # so a fixed grid drifts by up to a few slots over the report
        best = None
        for d in np.arange(-1.0, 1.0, tw):
            b = base + d
            sc = frac(b) + frac(b + SLOT) + frac(b + 2 * SLOT) - frac(b + 3 * SLOT) - frac(b - SLOT)
            if best is None or sc > best[0]: best = (sc, b)
        base = best[1]
        bits = [1 if frac(base + s * SLOT + 0.01) > 0.5 else 0 for s in range(22)]
        ok = bits[:4] == [1, 1, 1, 0] and bits[20:] == [0, 0]
        vals.append(int("".join(map(str, bits[4:20])), 2) if ok else None)
        base = base + 22 * SLOT
    return y, start, vals


def decode_runs(path):
    """Run-length decoding: the module skips some blocks, which stretches slots, so read the report as runs of
    muted / unmuted audio and round each run to whole slots; frames are re-aligned on their 1 1 1 0 preamble."""
    y = load2(path); m = 0.5 * (y[:, 0] + y[:, 1]); e = env(m); med = np.median(e[e > 0]); tw = 64 / FS
    low = e < 0.1 * med
    _, start, _ = decode(path)
    if start is None: return y, None, []
    i = int(start / tw); bits = []
    end = min(len(low), i + int((22 * len(NAMES) * SLOT * 1.15) / tw))
    while i < end:
        j = i
        while j < end and low[j] == low[i]: j += 1
        n = max(1, int(round((j - i) * tw / SLOT)))
        bits += [1 if low[i] else 0] * n
        i = j
    vals = []; k = 0
    for f in range(len(NAMES)):
        while k + 4 <= len(bits) and bits[k:k + 4] != [1, 1, 1, 0]: k += 1
        fr = bits[k:k + 22]
        vals.append(int("".join(map(str, fr[4:20])), 2) if len(fr) == 22 else None)
        k += 22
    return y, start, vals


def audio_test(y, start):
    """Level of L and R per second, for the 6 s before the report started (minus the bench)."""
    out = []
    t_audio = start - (6 * BPS) - 0.1 - 32 * 64 / FS * 2
    for s in range(6):
        a = int((t_audio + s * BPS + 0.15) * FS); b = int((t_audio + (s + 1) * BPS - 0.15) * FS)
        L = 20 * np.log10(np.std(y[a:b, 0]) + 1e-9); R = 20 * np.log10(np.std(y[a:b, 1]) + 1e-9)
        out.append((round(float(L), 2), round(float(R), 2)))
    return t_audio, out


def report(path):
    y, start, v = decode(path)
    y2, s2, v2 = decode_runs(path)
    v = [a if a is not None else b for a, b in zip(v, v2)] if v2 else v
    print("  run-length decode:", v2)
    print(os.path.basename(path), "report start", start)
    if start is None: print("  no report found"); return
    for k, x in enumerate(v): print(f"  {k:2d} {NAMES[k]:40s} = {x if x is not None else 'unreadable'}" + (f"  (0x{x:04X})" if x is not None else ""))
    ta, lv = audio_test(y, start)
    print(f"  audio test from {ta:.2f} s, level per second (L dB, R dB); expected L-6, R-6, both 0, then again:")
    for s, (L, R) in enumerate(lv): print(f"     second {s}: L {L:6.1f}  R {R:6.1f}")
    if v[0] == 0xA55A and None not in v[4:12]:
        ov = v[5] or 0
        for i in (6, 7, 8, 9):
            if v[i]: print(f"  {NAMES[i]:40s} {max(v[i] - ov, 1) / 1024:6.2f} cycles per multiply-add")
        for i in (10, 11):
            if v[i]: print(f"  {NAMES[i]:40s} {max(v[i] - ov, 1) / 32:7.1f} cycles per sample per layer"
                           f"  -> 23 layers: {max(v[i] - ov, 1) / 32 * 23:7.0f} cycles per sample")
        print(f"  flags: armed={bool(v[12] & 1)} stack={bool(v[12] & 2)} image={bool(v[12] & 4)};  block period {v[4] * 16} ticks")


def run():
    import sounddevice as sd, pmaudio, pmpreset
    from pmflash import Link
    from cut1_variants import read_p, describe
    from cut1_matrix import send, set_mod
    link = Link(); orig = read_p(link); link.close()
    rec = orig
    for k in range(10): rec = set_mod(rec, k, on=False)
    rec = set_mod(rec, 1, FXID, [0.0] * 8, True)
    print("probe preset: on =", describe(rec))
    path = os.path.join(RE, "audio", time.strftime("%Y%m%d-%H%M%S") + "-fx1probe.wav")
    secs = 80
    t = np.arange(int(FS * (secs + 3))) / FS; tone = (0.1 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
    p = pmaudio.record(path, secs); time.sleep(1.0)
    sd.play(np.stack([tone, tone], 1), samplerate=FS, device=pmaudio.out_device("External Headphones"))
    time.sleep(2.0)
    send(rec); time.sleep(3.5)
    try:
        link = Link(); pmpreset.write_message(link, b"\x11\x48", struct.pack("<IIf", 1, 0, 1.0)); link.close()
        print("armed (live edit FX1 Depth = 1, not saved)")
    except Exception as e:
        print("arming failed:", e)
    p.wait(); sd.stop()
    send(orig); time.sleep(0.5)
    link = Link(); back = read_p(link); link.close()
    print("P08 restored:", "OK (byte-identical)" if back[4:] == orig[4:] else "MISMATCH")
    report(path)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["run"]: run()
    elif len(a) == 2 and a[0] == "decode": report(a[1])
    else: sys.exit(__doc__)
