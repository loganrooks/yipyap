"""Generate per-letter stats and pitch summary for each josh voice."""
from __future__ import annotations

import numpy as np
import soundfile as sf
import librosa
from pathlib import Path

ROOT = Path("/home/rookslog/workspace/projects/yipyap/spikes")

VOICES = [
    "samples-josh-f1", "samples-josh-f2", "samples-josh-f3", "samples-josh-f4",
    "samples-josh-m1", "samples-josh-m2", "samples-josh-m3", "samples-josh-m4",
    "samples-josh-korean-f1",
    "samples-baseline",  # acedio for comparison
    "samples-equalo",    # comparison
    "samples-digiduncan",
]

def stats_for_voice(d: Path):
    rows = []
    pitches = []
    for letter in "abcdefghijklmnopqrstuvwxyz":
        p = d / f"{letter}.wav"
        if not p.exists():
            continue
        audio, sr = sf.read(str(p), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        peak = float(np.max(np.abs(audio)))
        rms = float(np.sqrt(np.mean(audio**2)))
        spec = np.abs(np.fft.rfft(audio))
        freqs = np.fft.rfftfreq(audio.size, 1 / sr)
        hf = float(spec[freqs > 5000].sum() / (spec.sum() + 1e-12))
        dc = float(np.mean(audio))
        # pyin pitch
        try:
            f0, _, _ = librosa.pyin(
                audio, fmin=80.0, fmax=600.0, sr=sr, frame_length=1024
            )
            valid = f0[~np.isnan(f0)] if f0 is not None else np.array([])
            f0_med = float(np.median(valid)) if valid.size else 0.0
        except Exception:
            f0_med = 0.0
        if f0_med > 0:
            pitches.append(f0_med)
        rows.append((letter, peak, rms, hf, dc, f0_med))
    return rows, pitches


print("# Per-voice summary\n")
print("| voice | n | peak_mean | rms_mean | hf5k_mean | pitch_med Hz | pitch_range Hz |")
print("|-------|--:|----------:|---------:|----------:|-------------:|---------------:|")
for v in VOICES:
    d = ROOT / v
    if not d.exists():
        print(f"| {v} | (missing) |")
        continue
    rows, pitches = stats_for_voice(d)
    peaks = [r[1] for r in rows]
    rmss = [r[2] for r in rows]
    hfs = [r[3] for r in rows]
    pmed = float(np.median(pitches)) if pitches else 0.0
    prange = f"{min(pitches):.0f}-{max(pitches):.0f}" if pitches else "n/a"
    print(
        f"| {v} | {len(rows)} | {np.mean(peaks):.3f} | "
        f"{np.mean(rmss):.3f} | {np.mean(hfs):.3f} | "
        f"{pmed:.1f} | {prange} |"
    )

# Detailed per-letter table for each josh voice
print("\n\n# Detailed per-letter (josh English voices)\n")
for v in [f"samples-josh-{x}" for x in ["f1","f2","f3","f4","m1","m2","m3","m4"]]:
    d = ROOT / v
    rows, pitches = stats_for_voice(d)
    print(f"\n## {v}")
    print("\n| ltr | peak | rms | hf5k | dc | f0 Hz |")
    print("|-----|-----:|----:|----:|---:|------:|")
    for letter, peak, rms, hf, dc, f0 in rows:
        f0s = f"{f0:.1f}" if f0 > 0 else "—"
        print(f"| {letter} | {peak:.3f} | {rms:.3f} | {hf:.3f} | {dc:+.4f} | {f0s} |")
