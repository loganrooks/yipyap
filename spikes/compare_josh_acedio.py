"""Compare josh's f1 against acedio's baseline to test if it's the same recording.

If josh is upsampled acedio: high cross-correlation peak at zero lag after
optimal time/scale alignment, similar spectrum shape, identical relative
duration ratios. If it's a different recording: low correlation, different
formant structure.

Scope: this script checks **josh-f1 only** against acedio (26 per-letter
pairs across the alphabet). It does NOT verify provenance for josh
f2/f3/f4 or m1/m2/m3/m4 — those voices' independence from acedio
specifically has not been measured here. The within-josh distinctness
argument relies on the per-voice f0/spectrum spread visible in
stats_josh.py / josh_stats_full.txt; pairwise cross-correlation among
the eight josh voices is NOT computed by any committed script. Any
provenance claim about the other seven voices needs to either commit
that pairwise check or stay grounded in the per-voice stats alone.

Run with the YIPYAP_SPIKES_ROOT env var to override the data root.

Prerequisite: both `samples-josh-f1/` and `samples-baseline/` must
exist under the data root before running. Populate them with:

    python spikes/extract_josh.py --josh-root <josh source>
        # writes samples-josh-f1/ (and the other voice banks)
    python spikes/00_extract_bank.py --out spikes/samples-baseline/
        # writes the acedio bank as samples-baseline/

The script aborts up-front (with a helpful error) if either directory
is missing, rather than failing partway through with a confusing
soundfile read error.
"""
from __future__ import annotations
import os
import sys
import numpy as np
import soundfile as sf
import librosa
from pathlib import Path

ROOT = Path(os.environ.get("YIPYAP_SPIKES_ROOT", str(Path(__file__).resolve().parent)))
JOSH_DIR = ROOT / "samples-josh-f1"
BASELINE_DIR = ROOT / "samples-baseline"

for required in (JOSH_DIR, BASELINE_DIR):
    if not required.exists():
        print(
            f"[compare] ERROR: required directory missing: {required}\n"
            f"          See module docstring for how to populate it.",
            file=sys.stderr,
        )
        sys.exit(2)

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
ja, jsr = sf.read(str(JOSH_DIR / "a.wav"))
aa, asr = sf.read(str(BASELINE_DIR / "a.wav"))
# Downmix stereo to mono before any resampling — librosa.resample on a
# 2-D array operates along the channel axis if you don't, which produces
# garbage. The per-letter loop below has the same guard.
if ja.ndim > 1:
    ja = ja.mean(axis=1)
if aa.ndim > 1:
    aa = aa.mean(axis=1)
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
    ja, jsr = sf.read(str(JOSH_DIR / f"{letter}.wav"))
    aa, asr = sf.read(str(BASELINE_DIR / f"{letter}.wav"))
    if ja.ndim > 1:
        ja = ja.mean(axis=1)
    if aa.ndim > 1:
        aa = aa.mean(axis=1)
    jr = librosa.resample(ja.astype(np.float32), orig_sr=jsr, target_sr=asr) if jsr != asr else ja
    cc = cross_correlate(jr.astype(np.float32), aa.astype(np.float32))
    xcorrs.append(cc)
print(f"  mean={np.mean(xcorrs):.3f}, median={np.median(xcorrs):.3f}, max={max(xcorrs):.3f}, min={min(xcorrs):.3f}")
print("  (xcorr >0.8 = effectively same waveform; <0.3 = unrelated recordings)")
