#!/usr/bin/env python3
"""USB audio loopback check: plays a quiet test tone to the pedal over USB and records the pedal's USB output.

  pmaudio.py loop [seconds]     play 1 kHz sine (-20 dBFS) to the pedal over USB while recording its USB output
  pmaudio.py jack [seconds]     play the tone from the Mac's headphone jack (cable -> pedal IN) while recording USB

Only audio is exchanged; nothing is sent to the pedal over MIDI. Recordings are saved in re/audio/.
"""
import os, sys, time, wave
import numpy as np
import sounddevice as sd

FS = 44100
OUTDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "audio")


def device():
    for i, d in enumerate(sd.query_devices()):
        if "Pocket Master" in d["name"] and d["max_input_channels"] >= 2 and d["max_output_channels"] >= 2:
            return i
    sys.exit("Pocket Master Audio not found")


def save(path, x):
    x16 = np.clip(x * 32767, -32768, 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(x.shape[1]); w.setsampwidth(2); w.setframerate(FS); w.writeframes(x16.tobytes())


def tone_region(x, margin_s=0.1):
    """Cut the recording to where the tone is present (envelope above 30% of its maximum)."""
    e = np.sqrt(np.convolve(x[:, 0] ** 2, np.ones(441) / 441, mode="same"))
    on = np.where(e > 0.3 * e.max())[0] if e.max() > 0 else []
    if len(on) == 0:
        return x
    m = int(margin_s * FS)
    return x[on[0] + m:on[-1] - m]


def analyse(x, f0=1000.0):
    """Per channel: RMS dBFS, fundamental level, THD (harmonics 2-10), noise floor, and gaps/clicks in the tone."""
    res = []
    for ch in range(x.shape[1]):
        y = x[:, ch]
        if len(y) < FS:
            res.append(None); continue
        rms = 20 * np.log10(np.sqrt(np.mean(y ** 2)) + 1e-12)
        n = 1 << int(np.floor(np.log2(len(y))))
        seg = y[:n] * np.hanning(n)
        sp = np.abs(np.fft.rfft(seg)) / (n / 4)
        fr = np.fft.rfftfreq(n, 1 / FS)
        def band(f):
            k = np.argmin(np.abs(fr - f)); return np.sqrt(np.sum(sp[max(k - 3, 0):k + 4] ** 2))
        fund = band(f0)
        harm = np.sqrt(sum(band(f0 * h) ** 2 for h in range(2, 11) if f0 * h < FS / 2))
        thd = 100 * harm / (fund + 1e-12)
        # tone continuity: envelope in 1 ms windows, count dips below 50% of median
        w = int(FS / 1000)
        env = np.sqrt(np.convolve(y ** 2, np.ones(w) / w, mode="valid"))[::w]
        med = np.median(env)
        dips = int(np.sum(env < 0.5 * med)) if med > 1e-4 else -1
        res.append(dict(rms_dbfs=round(rms, 1), fundamental_dbfs=round(20 * np.log10(fund + 1e-12), 1),
                        thd_percent=round(thd, 2), dips_1ms=dips))
    return res


def ffmpeg_record(path, seconds):
    import subprocess
    lst = subprocess.run(["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                         capture_output=True, text=True).stderr
    idx = next(l.split("[")[2].split("]")[0] for l in lst.splitlines() if "Pocket Master" in l and "] [" in l)
    return subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "avfoundation", "-i", f":{idx}",
                             "-t", str(seconds), "-ac", "2", "-ar", str(FS), path])


class _SdRec:
    """Gap-free recording of the pedal's USB output with PortAudio (callback stream)."""
    def __init__(self, path, seconds):
        import threading
        self.path, self.seconds, self.chunks = path, seconds, []
        self.t = threading.Thread(target=self._run, daemon=True); self.t.start()

    def _run(self):
        def cb(indata, frames, ti, status):
            self.chunks.append(indata.copy())
        with sd.InputStream(device=device_in(), channels=2, samplerate=FS, dtype="float32", callback=cb, latency="high"):
            time.sleep(self.seconds)
        save(self.path, np.concatenate(self.chunks)[:int(self.seconds * FS)])

    def wait(self):
        self.t.join()


def record(path, seconds):
    """Record the pedal's USB output (use this instead of ffmpeg_record: ffmpeg/AVFoundation drops ~7 % of the
    samples from this device, measured 2026-11-17: 20 s requested -> 18.6 s of audio, tone at 998 instead of 1000 Hz)."""
    return _SdRec(path, seconds)


def device_in():
    for i, d in enumerate(sd.query_devices()):
        if "Pocket Master" in d["name"] and d["max_input_channels"] >= 2:
            return i
    sys.exit("Pocket Master Audio input not found")


def out_device(name):
    for i, d in enumerate(sd.query_devices()):
        if name in d["name"] and d["max_output_channels"] >= 2:
            return i
    sys.exit(f"output device {name!r} not found")


def loop(seconds=6.0, via_jack=False):
    dev = device()
    os.makedirs(OUTDIR, exist_ok=True)
    t = np.arange(int(FS * seconds)) / FS
    tone = (0.1 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)        # -20 dBFS
    fade = np.minimum(1, np.minimum(t, t[::-1]) / 0.05).astype(np.float32)
    play = np.stack([tone * fade, tone * fade], axis=1)
    sd.default.samplerate = FS
    if via_jack:
        # Recording via PortAudio returns pure zeros from this device; ffmpeg (AVFoundation) records it correctly.
        out = out_device("External Headphones")
        tmp = os.path.join(OUTDIR, "_capture.wav")
        rec_proc = ffmpeg_record(tmp, seconds + 1.5)
        time.sleep(0.8)
        sd.play(play, samplerate=FS, device=out)
        sd.wait()
        rec_proc.wait()
        with wave.open(tmp) as w:
            rec = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32).reshape(-1, 2) / 32768
        os.remove(tmp)
    else:
        sd.default.device = (dev, dev)
        rec = sd.playrec(play, channels=2, dtype="float32")
        sd.wait()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    save(os.path.join(OUTDIR, f"{stamp}-played.wav"), play)
    save(os.path.join(OUTDIR, f"{stamp}-recorded.wav"), rec)
    print("played  :", analyse(play))
    print("recorded:", analyse(tone_region(rec)))
    print("saved in", OUTDIR, "as", stamp + "-*.wav")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] in ("loop", "jack"):
        loop(float(a[1]) if len(a) > 1 else 6.0, via_jack=a[0] == "jack")
    else:
        sys.exit(__doc__)
