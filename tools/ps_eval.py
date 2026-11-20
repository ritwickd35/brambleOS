#!/usr/bin/env python3
"""ps_eval.py: offline pitch-shifter check on a 440 Hz tone and a guitar clip: tuning of the shifted voices (cents) and
the energy outside the intended tones (dB)."""
import numpy as np, subprocess, os, sys
RE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
x = (0.3 * np.sin(2 * np.pi * 440 * np.arange(44100 * 3) / 44100)).astype("<f4")
y = np.frombuffer(subprocess.run([os.path.join(RE, "dsp", "host"), "octave"] + sys.argv[1:4], input=x.tobytes(), capture_output=True).stdout, "<f4")[44100:].astype(float)
X = np.abs(np.fft.rfft(y * np.hanning(len(y)))) ** 2; f = np.fft.rfftfreq(len(y), 1 / 44100)
def peak(f0): i = np.argmin(abs(f - f0)); j = i - 40 + int(np.argmax(X[i - 40:i + 40])); return f[j], j
for f0 in (220, 880):
    fp, j = peak(f0); print(f"voice {f0} Hz: measured {fp:.1f} Hz ({1200 * np.log2(fp / f0):+.1f} cents)")
keep = sum(X[peak(a)[1] - 20:peak(a)[1] + 20].sum() for a in (220, 440, 880))
print(f"junk outside the three tones: {10 * np.log10((X.sum() - keep) / X.sum()):.1f} dB")
