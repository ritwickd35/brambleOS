#!/usr/bin/env python3
"""Identify the pedal's clone engine: upload test clones to slot 5, play a fixed probe signal through P08 in Clone
mode (everything else off), save recordings to audio/cloneprobe/<name>.npy (aligned to the probe).
  clone_probe.py run <name>=<clo file or 'gen:<spec>'> ...     spec: fa=d<k>,fb=d<k>,p=a/b/c/d
  clone_probe.py bypass                                         reference recording with every block off
Probe (44.1 kHz, mono): click, noise -25 dBFS 4 s, sine 220 Hz ramp -50..-3 dBFS 3 s, DI guitar (peak 0.9) 4 s."""
import os, sys, time, struct
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
import pmclone as P
FS = 44100; OUT = os.path.join(RE, "audio", "cloneprobe"); SLOT = 5; CLO_FX = 0x0F000000 + SLOT - 1


def probe():
    r = np.random.default_rng(7); s = lambda t: np.zeros(int(t * FS))
    click = np.r_[1.0, np.zeros(99)] * 0.5
    noise = r.standard_normal(4 * FS) * 10 ** (-25 / 20)
    t = np.arange(3 * FS) / FS; sine = np.sin(2 * np.pi * 220 * t) * 10 ** ((-50 + 47 * t / 3) / 20)
    di = np.fromfile(os.path.join(RE, "audio", "di_reference_44100.f32"), "<f4")[int(5 * FS):int(9 * FS)].astype(float)
    di *= 0.9 / np.max(np.abs(di))
    parts = [s(0.4), click, s(0.5), noise, s(0.4), sine, s(0.4), di, s(0.6)]
    return np.concatenate(parts).astype(np.float32)


SEG = {}                                                      # name -> (start, end) samples in the probe
def segs():
    L = [("pre", 0.4), ("click", 100 / FS), ("gap", 0.5), ("noise", 4), ("gap2", 0.4), ("sine", 3), ("gap3", 0.4), ("di", 4)]
    o = 0
    for n, d in L: SEG[n] = (o, o + int(round(d * FS))); o += int(round(d * FS))
segs()


def gen(spec):
    d = dict(kv.split("=") for kv in spec.split(","))
    def taps(v, n):                                   # "d0+0.5d300": unit tap at 0, half tap at 300
        h = np.zeros(n)
        for t in v.split("+"):
            g, k = t.split("d"); h[int(k)] += float(g) if g else 1.0
        return h
    p = [float(x) for x in d.get("p", "0.0616/0.0606/546.27/624.13").split("/")]
    return P.build(dict(bqa=np.r_[1.0, 0, 0, 0, 0], bqb=np.r_[1.0, 0, 0, 0, 0], p=np.array(p), fa=taps(d.get("fa", "d0"), 128), fb=taps(d.get("fb", "d0"), 512)))


class Rig:
    def __init__(self):
        import sounddevice as sd, pmaudio
        from pmflash import Link
        from cut1_variants import read_p
        from cut1_matrix import send, set_mod
        self.sd, self.pa, self.Link, self.read_p, self.send, self.S = sd, pmaudio, Link, read_p, send, set_mod
        self.dev = pmaudio.out_device("External Headphones")
        l = Link(); self.orig = read_p(l); l.close()
        u = self.orig
        for k in range(10): u = set_mod(u, k, on=False)
        self.off = u
        self.clone = set_mod(set_mod(u, 3, None, [50.0] * 8, True), 9, CLO_FX, [50.0] * 8, True)

    def take(self, rec):
        x = probe(); path = f"/tmp/cloneprobe-{os.getpid()}.wav"
        self.send(rec); time.sleep(1.5)
        for _ in range(3):
            if os.path.exists(path): os.remove(path)
            p = self.pa.record(path, len(x) / FS + 1.0); time.sleep(0.3)
            self.sd.play(np.stack([x, x], 1), samplerate=FS, device=self.dev); p.t.join(len(x) / FS + 20); self.sd.stop()
            if p.t.is_alive():                                    # the recording hung: reset the audio system
                print("   recording hung, resetting audio", flush=True); self.sd._terminate(); time.sleep(2); self.sd._initialize()
                self.dev = self.pa.out_device("External Headphones"); continue
            if os.path.exists(path): break
        import wave
        w = wave.open(path); y = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2).astype(float).mean(1) / 32768
        c0 = int(np.argmax(np.abs(y[:int(1.1 * FS)])))    # recording starts ~0.3 s before playback: click ~0.7 s, music >= 1.2 s      # the click = loudest sample before the music (a high-gain
                                                             # clone's hiss can cross a fixed threshold earlier)
        st = c0 - SEG["click"][0]
        if st < 0 and os.environ.get("CLICKDBG"): print(f"   click at {c0 / FS:.3f} s, expected after {SEG['click'][0] / FS:.3f} s, peak {np.abs(y[:int(1.1 * FS)]).max():.3f}", flush=True)
        if st < 0: y = np.r_[np.zeros(-st), y]; st = 0      # recording started late: pad (the click is still found)
        return y[st:st + len(x)] if len(y) >= st + len(x) else None

    def restore(self):
        self.send(self.orig); time.sleep(0.5); l = self.Link(); b = self.read_p(l); l.close(); return b[4:] == self.orig[4:]


def main():
    os.makedirs(OUT, exist_ok=True); a = sys.argv[1:]; rig = Rig()
    try:
        if a[0] == "bypass":
            np.save(os.path.join(OUT, "bypass.npy"), rig.take(rig.off)); print("bypass saved")
        for job in a[1:] if a[0] == "run" else []:
            name, src = job.split("=", 1)
            clo = gen(src[4:]) if src.startswith("gen:") else open(src, "rb").read()
            P.upload(clo, SLOT, "probe " + name[:9])
            rig.send(rig.S(rig.clone, 9, CLO_FX - 1)); time.sleep(0.8)      # select another slot, then ours: reload
            y = rig.take(rig.clone); np.save(os.path.join(OUT, f"{name}.npy"), y)
            lv = lambda s: round(float(20 * np.log10(np.std(y[SEG[s][0]:SEG[s][1]]) + 1e-12)), 1)
            print(f"{name}: noise {lv('noise')} dB, sine {lv('sine')} dB, di {lv('di')} dB", flush=True)
    finally:
        print("P08 restored", rig.restore())


if __name__ == "__main__":
    main()
