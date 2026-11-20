#!/usr/bin/env python3
"""Cut 1 CPU headroom test: plays a steady 1 kHz tone into the pedal (Mac headphone jack -> cable -> pedal IN),
records the pedal's USB output for ~110 s, and finds the load-test module's time marker and overload glitches.

  pmloadtest.py run [seconds]      record + analyse (select "CPU Test 1" in the DRV block once it says so)
  pmloadtest.py analyse <wav>      analyse an existing recording

The module ("CPU Test 1", firmware cut1) repeats 3 cycles: 1 marker glitch, 2 s rest, then +1 % extra load every
0.25 s until the DSP overruns, then 4 s rest. Headroom % = steps between marker+2 s and the overload glitch.
"""
import os, sys, time, wave
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import pmaudio
import sounddevice as sd

FS = 44100
OUT = pmaudio.OUTDIR


def load(path):
    with wave.open(path) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32).reshape(-1, 2)[:, 0] / 32768


def glitches(y):
    """Return times (s) of short dropouts/clicks in a steady tone."""
    w = 32                                                   # 0.7 ms windows
    n = len(y) // w
    env = np.sqrt(np.mean(y[:n * w].reshape(n, w) ** 2, axis=1))
    # high-frequency click energy: second difference
    d2 = np.abs(np.diff(y, 2))[:n * w - 2]
    d2 = np.concatenate([d2, [0, 0]])[:n * w].reshape(n, w).max(axis=1)
    on = env > 0.3 * np.median(env[env > 0]) if np.any(env > 0) else np.zeros(n, bool)
    # "inside the tone": 50 ms average level is high, and we are at least 50 ms away from the tone's start/end
    long = np.convolve(env, np.ones(69) / 69, mode="same")
    present = long > 0.3 * np.median(long[long > 0]) if np.any(long > 0) else np.zeros(n, bool)
    live = np.convolve(present.astype(float), np.ones(141) / 141, mode="same") > 0.999
    med_env = np.median(env[on]) if np.any(on) else 0
    med_d2 = np.median(d2[on]) if np.any(on) else 0
    bad = live & (env < 0.5 * med_env)          # dropouts only; distortion makes click detection unreliable
    t = np.where(bad)[0] * w / FS
    events = []
    for x in t:                                              # merge hits closer than 20 ms
        if not events or x - events[-1][1] > 0.02:
            events.append([x, x])
        else:
            events[-1][1] = x
    return [(round(a, 3), round(b - a + w / FS, 4)) for a, b in events]


def interpret(ev):
    """Clusters (glitches within 0.3 s). A marker is 1 cluster, or 2 clusters ~0.5 s apart (no cycle counter).
    The ramp starts 2 s after the (last) marker; the next cluster >= 1.9 s later is the overload."""
    cl = []
    for t, _ in ev:
        if cl and t - cl[-1][1] < 0.3:
            cl[-1][1] = t
        else:
            cl.append([t, t])
    res, i = [], 0
    while i + 1 < len(cl):
        m = cl[i]
        j = i + 1
        double = cl[j][0] - m[0] < 0.8
        if double:
            m = cl[j]; j += 1
            if j >= len(cl):
                break
        o = cl[j]
        if o[0] - m[1] >= 1.9:
            k = (o[0] - m[0] - 2.0) / 0.25 + 1
            res.append(dict(marker_s=round(m[0], 3), overload_s=round(o[0], 3), headroom_percent=round(k),
                            cycle_counter="no" if double else "yes"))
            i = j + 1
        else:
            i = j
    return res


def report(path):
    y = load(path)
    ev = glitches(y)
    print(f"{os.path.basename(path)}: {len(y) / FS:.1f} s, {len(ev)} glitch events")
    for t, dur in ev:
        print(f"   glitch at {t:7.3f} s  ({dur * 1000:.1f} ms)")
    r = interpret(ev)
    for c, x in enumerate(r, 1):
        print(f" cycle {c}: marker {x['marker_s']:.2f} s, overload {x['overload_s']:.2f} s  ->  free CPU ~ {x['headroom_percent']} % of one block")
    if not r:
        print(" no marker/overload pairs found")
    return r


def run(seconds=110.0):
    os.makedirs(OUT, exist_ok=True)
    out = pmaudio.out_device("External Headphones")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(OUT, f"{stamp}-cputest.wav")
    t = np.arange(int(FS * (seconds + 2))) / FS
    tone = (0.1 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
    rec = pmaudio.record(path, seconds)
    time.sleep(0.8)
    sd.play(np.stack([tone, tone], 1), samplerate=FS, device=out)
    print(">>> Recording. Now select 'CPU Test 1' in the DRV block (DRV switched on), then do not touch the pedal.")
    for s in range(int(seconds), 0, -10):
        print(f"   {s} s left", flush=True)
        time.sleep(min(10, s))
    rec.wait(); sd.stop()
    print("saved", path)
    report(path)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "run":
        run(float(a[1]) if len(a) > 1 else 110.0)
    elif len(a) == 2 and a[0] == "analyse":
        report(a[1])
    else:
        sys.exit(__doc__)
