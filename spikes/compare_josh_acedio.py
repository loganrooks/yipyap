"""Compare josh's f1 against acedio's baseline to test if it's the same recording.

If josh is upsampled acedio: high cross-correlation peak at zero lag after
optimal time/scale alignment, similar spectrum shape, identical relative
duration ratios. If it's a different recording: low correlation, different
formant structure.

Scope: this script checks **josh-f1 only** against acedio (26 per-letter
pairs across the alphabet). It does NOT verify provenance for josh
f2/f3/f4 or m1/m2/m3/m4 — those voices were inspected via cross-
correlation among themselves in stats_josh.py / josh_stats_full.txt
but their independence from acedio specifically has not been measured
here. Any provenance claim about the other seven voices must rely on
the within-josh distinctness check, not on this script.

Run with the YIPYAP_SPIKES_ROOT env var to override the data root.
"""
from __future__ import annotations
import os
import numpy as np
import soundfile as sf
import librosa
from pathlib import Path

ROOT = Path(os.environ.get("YIPYAP_SPIKES_ROOT", str(Path(__file__).resolve().parent)))

def cross_correlate(a, b):
    """Max-normalized cross-correlation peak between two signals at common SR."""
    n = min(a.size, b.size)
    a = a[:n] - a[:n].mean()
    b = b[:n] - b[:n].mean()
    aa = float(np.sqrt(np.sum(a*a)))
    bb = float(np.sqrt(np.sum(b*b)))
    if aa == 0 or bb == 0:
        return 0.0
    return float(np.max(np.correlate(a / aa, b / bb, mode="full")))

def spectral_centroid_hz(x, sr):
    return float(np.mean(librosa.feature.spectral_centroid(y=x, sr=sr)))

print("Comparing josh f1 'a' against acedio baseline 'a':")
ja, jsr = sf.read(str(ROOT / "samples-josh-f1" / "a.wav"))
aa, asr = sf.read(str(ROOT / "samples-baseline" / "a.wav"))
print(f"  josh f1 a: {ja.size} samples @ {jsr} = {ja.size/jsr*1000:.0f}ms")
print(f"  acedio a:  {aa.size} samples @ {asr} = {aa.size/asr*1000:.0f}ms")

# Resample josh to same length as acedio for direct comparison
jr = librosa.resample(ja.astype(np.float32), orig_sr=jsr, target_sr=asr) if jsr != asr else ja
jr = jr / (np.max(np.abs(jr)) + 1e-9)
ar = aa / (np.max(np.abs(aa)) + 1e-9)

# Cross-correlation
ccmax = cross_correlate(jr.astype(np.float32), ar.astype(np.float32))
print(f"  max xcorr (peak-normalized): {ccmax:.3f}")

# Spectral centroid (timbre signature)
print(f"  josh f1 a centroid:  {spectral_centroid_hz(jr.astype(np.float32), asr):.0f} Hz")
print(f"  acedio a centroid:   {spectral_centroid_hz(ar.astype(np.float32), asr):.0f} Hz")

# Across all letters: average xcorr
print("\nPer-letter xcorr (josh-f1 vs acedio):")
xcorrs = []
for letter in "abcdefghijklmnopqrstuvwxyz":
    ja, jsr = sf.read(str(ROOT / "samples-josh-f1" / f"{letter}.wav"))
    aa, asr = sf.read(str(ROOT / "samples-baseline" / f"{letter}.wav"))
    if ja.ndim > 1: ja = ja.mean(axis=1)
    if aa.ndim > 1: aa = aa.mean(axis=1)
    jr = librosa.resample(ja.astype(np.float32), orig_sr=jsr, target_sr=asr) if jsr != asr else ja
    cc = cross_correlate(jr.astype(np.float32), aa.astype(np.float32))
    xcorrs.append(cc)
print(f"  mean={np.mean(xcorrs):.3f}, median={np.median(xcorrs):.3f}, max={max(xcorrs):.3f}, min={min(xcorrs):.3f}")
print("  (xcorr >0.8 = effectively same waveform; <0.3 = unrelated recordings)")
