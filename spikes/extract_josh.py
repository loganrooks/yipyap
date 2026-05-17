"""Extract josh's voice sprite-strips into per-letter .wav files.

Each josh .ogg is 48 kHz stereo Vorbis, sprite layout per
/tmp/josh/utils/audio-manager.cjs lines 28-67: a-z at 200ms intervals,
then 0-9, then ok/gwah/deska. We extract a-z only (the bank yipyap uses)
into 44.1 kHz mono 16-bit PCM .wav at 200ms per letter.

Downmix stereo -> mono by averaging. Resample 48k -> 44.1k via
scipy.signal.resample_poly (Kaiser-windowed polyphase, anti-aliased).
Peak-normalize each letter to 0.95 (matches 00_extract_bank.py output).
Apply 5ms linear fades at start/end to avoid clicks.
"""
from __future__ import annotations

import sys
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

SRC_SR = 48_000
TARGET_SR = 44_100
LETTER_S = 0.200
N_LETTERS = 26
PEAK_NORM = 0.95
FADE_S = 0.005

JOSH_ROOT = Path("/tmp/josh/assets/audio/voice")
YIPYAP_SPIKES = Path("/home/rookslog/workspace/projects/yipyap/spikes")


def extract_voice(ogg_path: Path, out_dir: Path) -> dict:
    """Slice one sprite-strip .ogg into 26 letter .wavs. Returns stats dict."""
    audio, sr = sf.read(str(ogg_path), dtype="float32", always_2d=False)
    if sr != SRC_SR:
        raise RuntimeError(f"{ogg_path}: expected {SRC_SR} Hz, got {sr}")
    if audio.ndim == 2:
        mono = audio.mean(axis=1).astype(np.float32)
    else:
        mono = audio.astype(np.float32)

    # Resample 48000 -> 44100 by ratio 147/160 (gcd-reduced).
    g = gcd(TARGET_SR, SRC_SR)
    up, down = TARGET_SR // g, SRC_SR // g
    mono_44k = resample_poly(mono, up, down).astype(np.float32)

    samples_per_letter = int(round(LETTER_S * TARGET_SR))  # 8820
    fade_n = max(1, int(FADE_S * TARGET_SR))
    fade_in = np.linspace(0.0, 1.0, fade_n, dtype=np.float32)
    fade_out = np.linspace(1.0, 0.0, fade_n, dtype=np.float32)

    out_dir.mkdir(parents=True, exist_ok=True)
    stats = {"path": str(ogg_path), "out_dir": str(out_dir), "letters": []}

    for i in range(N_LETTERS):
        start = i * samples_per_letter
        end = start + samples_per_letter
        if end > mono_44k.size:
            raise RuntimeError(
                f"{ogg_path}: source too short for letter {chr(ord('a')+i)} "
                f"(need {end} samples, have {mono_44k.size})"
            )
        chunk = mono_44k[start:end].copy()
        # Subtract per-letter DC offset.
        chunk = (chunk - float(np.mean(chunk))).astype(np.float32)
        peak_raw = float(np.max(np.abs(chunk)))
        if peak_raw > 0:
            chunk = (chunk / peak_raw * PEAK_NORM).astype(np.float32)
        chunk[:fade_n] *= fade_in
        chunk[-fade_n:] *= fade_out

        letter = chr(ord("a") + i)
        out_path = out_dir / f"{letter}.wav"
        sf.write(out_path, chunk, TARGET_SR, subtype="PCM_16")

        peak = float(np.max(np.abs(chunk)))
        rms = float(np.sqrt(np.mean(chunk**2)))
        spec = np.abs(np.fft.rfft(chunk))
        freqs = np.fft.rfftfreq(chunk.size, 1 / TARGET_SR)
        hf = float(spec[freqs > 5000].sum() / (spec.sum() + 1e-12))
        dc = float(np.mean(chunk))
        stats["letters"].append({
            "letter": letter, "peak": peak, "rms": rms,
            "hf5k": hf, "dc": dc, "peak_raw_pre_norm": peak_raw,
        })
    return stats


def summarize(stats: dict) -> str:
    """One-line health summary per voice."""
    letters = stats["letters"]
    peaks = [l["peak"] for l in letters]
    rmss = [l["rms"] for l in letters]
    hfs = [l["hf5k"] for l in letters]
    raw_peaks = [l["peak_raw_pre_norm"] for l in letters]
    anom = []
    for l in letters:
        if l["peak"] > 0.99:
            anom.append(f"clip:{l['letter']}({l['peak']:.3f})")
        if l["peak_raw_pre_norm"] < 0.05:
            anom.append(f"silent:{l['letter']}({l['peak_raw_pre_norm']:.3f})")
        if abs(l["dc"]) > 0.01:
            anom.append(f"dc:{l['letter']}({l['dc']:+.3f})")
    return (
        f"  letters={len(letters)} peak_mean={np.mean(peaks):.3f} "
        f"rms_mean={np.mean(rmss):.3f} hf_mean={np.mean(hfs):.3f} "
        f"raw_peak_mean={np.mean(raw_peaks):.3f} "
        f"anomalies={anom if anom else 'none'}"
    )


def main() -> int:
    targets = [
        # (ogg path, out dir)
        (JOSH_ROOT / "english" / "f1.ogg", YIPYAP_SPIKES / "samples-josh-f1"),
        (JOSH_ROOT / "english" / "f2.ogg", YIPYAP_SPIKES / "samples-josh-f2"),
        (JOSH_ROOT / "english" / "f3.ogg", YIPYAP_SPIKES / "samples-josh-f3"),
        (JOSH_ROOT / "english" / "f4.ogg", YIPYAP_SPIKES / "samples-josh-f4"),
        (JOSH_ROOT / "english" / "m1.ogg", YIPYAP_SPIKES / "samples-josh-m1"),
        (JOSH_ROOT / "english" / "m2.ogg", YIPYAP_SPIKES / "samples-josh-m2"),
        (JOSH_ROOT / "english" / "m3.ogg", YIPYAP_SPIKES / "samples-josh-m3"),
        (JOSH_ROOT / "english" / "m4.ogg", YIPYAP_SPIKES / "samples-josh-m4"),
        (JOSH_ROOT / "korean" / "f1.ogg", YIPYAP_SPIKES / "samples-josh-korean-f1"),
    ]
    all_stats = []
    for src, dst in targets:
        print(f"[extract] {src.name} ({src.parent.name}) -> {dst.name}/")
        st = extract_voice(src, dst)
        print(summarize(st))
        all_stats.append((src.parent.name + "/" + src.stem, dst, st))

    # Verify each output dir has exactly 26 .wav files
    print("\n[verify] file counts:")
    for label, dst, _ in all_stats:
        n = len(list(dst.glob("*.wav")))
        marker = "OK" if n == 26 else "FAIL"
        print(f"  [{marker}] {dst.name}: {n} .wav files")

    return 0


if __name__ == "__main__":
    sys.exit(main())
