#!/usr/bin/env python3
"""Measure the 16 factory cabs as the pedal applies them: P08 with only the IR slot on, exponential sine sweep in,
USB out, deconvolved against the bypass take (removes the Mac/pedal converters). Writes audio/cabcap/<name>.f32
(impulse response, 44.1 kHz, 4096 samples) and logs/cabcap.json. P08 restored byte-identically."""
import json, os, struct, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RE = os.path.dirname(HERE); sys.path.insert(0, HERE)
FS = 44100; T = 3.0; OUT = os.path.join(RE, "audio", "cabcap" + os.environ.get("CABCAP_TAG", ""))
CABS = [(1, "TWD 1x8"), (2, "TWD-P 1x10"), (4, "Viblux 1x12"), (8, "Voks 1x12"), (27, "TWD 2x12"), (18, "Double 2x12"),
        (25, "Star 2x12"), (17, "Jazz 2x12"), (19, "BritGN 2x12"), (34, "BritGN 4x12"), (39, "Bog 4x12"), (46, "Dizzy 4x12"),
        (32, "Halen 4x12"), (40, "Sol 4x12"), (36, "Dual 4x12"), (30, "Bass 4x10")]


def sweep():
    t = np.arange(int(T * FS)) / FS; f0, f1 = 20.0, 20000.0; L = T / np.log(f1 / f0)
    x = 0.1 * np.sin(2 * np.pi * f0 * L * (np.exp(t / L) - 1)); x[:200] *= np.linspace(0, 1, 200); x[-200:] *= np.linspace(1, 0, 200)
    return np.r_[np.zeros(FS // 2), x, np.zeros(FS)].astype(np.float32)


def deconv(y, ref, n=4096):
    N = 1 << int(np.ceil(np.log2(len(y) + len(ref)))); Y = np.fft.rfft(y, N); R = np.fft.rfft(ref, N)
    H = Y * np.conj(R) / (np.abs(R) ** 2 + 1e-3 * np.max(np.abs(R)) ** 2); h = np.fft.irfft(H, N)
    k = int(np.argmax(np.abs(h[:N // 2]))); return h[max(k - 64, 0):max(k - 64, 0) + n]


def main():
    import sounddevice as sd, pmaudio, eprobe_decode as D
    from pmflash import Link
    from cut1_variants import read_p
    from cut1_matrix import send, set_mod
    x = sweep(); dev = pmaudio.out_device("External Headphones"); os.makedirs(OUT, exist_ok=True)
    l = Link(); orig = read_p(l); l.close(); base = orig
    for k in range(10): base = set_mod(base, k, on=False)
    def take(rec):
        send(rec); time.sleep(3.0); p = pmaudio.record("/tmp/cab.wav", len(x) / FS + 1.5); time.sleep(0.3)
        sd.play(np.stack([x, x], 1), samplerate=FS, device=dev); p.wait(); sd.stop(); return D.load("/tmp/cab.wav").astype(float)
    res = {}
    try:
        ref = take(base)
        for k, nm in [c for c in CABS if not os.environ.get('CABS') or c[1] in os.environ['CABS'].split(',')]:
            y = take(set_mod(base, 4, 167772160 + k, [50.0] + [0.0] * 7, True)); h = deconv(y, ref)
            h.astype("<f4").tofile(os.path.join(OUT, nm.replace(" ", "_") + ".f32"))
            e = np.cumsum(h[::-1] ** 2)[::-1]; e /= e[0]
            res[nm] = dict(len_60dB=int(np.argmax(e < 1e-6)), len_40dB=int(np.argmax(e < 1e-4)), rec_peak=round(float(np.max(np.abs(y))), 3), rec_rms_db=round(float(20 * np.log10(np.std(y[FS:]) + 1e-12)), 1))
            print(time.strftime("%H:%M:%S"), nm, res[nm], flush=True)
        json.dump(res, open(os.path.join(RE, "logs", "cabcap" + os.environ.get("CABCAP_TAG", "") + ".json"), "w"), indent=1)
    finally:
        send(orig); time.sleep(0.5); l = Link(); back = read_p(l); l.close(); print("P08 restored:", back[4:] == orig[4:])


if __name__ == "__main__":
    main()
