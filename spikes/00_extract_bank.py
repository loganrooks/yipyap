"""Spike bootstrap: extract 26 A-Z animalese letter samples from animalese.js.

The animalese letter bank at ``spikes/samples/`` is gitignored — the upstream
``animalese.wav`` is from `acedio/animalese.js`_ and we don't redistribute
it, only the slicer that regenerates the bank from source.

The source WAV is 3.9s of PCM_U8 mono at 44.1 kHz: 26 letters laid out
back-to-back, each 0.15s (6615 samples). This script downloads that file,
slices it into 26 chunks, subtracts per-letter DC offset (so the cut
starts at zero), peak-normalizes each chunk to 0.95, applies short
linear fades at the edges so per-letter cuts don't click, and writes
``{a..z}.wav`` (PCM_16, mono, 44.1 kHz, 0.15s) into the target directory.

Run once per fresh checkout::

    python spikes/00_extract_bank.py
    # or to a custom location:
    python spikes/00_extract_bank.py --out /tmp/bank/

.. _acedio/animalese.js: https://github.com/acedio/animalese.js
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

SOURCE_URL = (
    "https://raw.githubusercontent.com/acedio/animalese.js/master/animalese.wav"
)
LETTER_DURATION_S = 0.15
N_LETTERS = 26
PEAK_NORM = 0.95
FADE_S = 0.005


def download_source(dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"[extract-bank] downloading {SOURCE_URL} -> {dest}")
    urllib.request.urlretrieve(SOURCE_URL, dest)
    return dest


def slice_letters(source_wav: Path, out_dir: Path) -> list[Path]:
    audio, sr = sf.read(str(source_wav), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1).astype(np.float32)

    samples_per_letter = int(LETTER_DURATION_S * sr)
    expected_total = samples_per_letter * N_LETTERS
    if audio.size < expected_total:
        raise RuntimeError(
            f"{source_wav.name} too short: {audio.size} samples, expected "
            f">= {expected_total} ({N_LETTERS} letters × "
            f"{LETTER_DURATION_S}s @ {sr}Hz). Wrong source file?"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    fade_n = max(1, int(FADE_S * sr))
    fade_in = np.linspace(0.0, 1.0, fade_n, dtype=np.float32)
    fade_out = np.linspace(1.0, 0.0, fade_n, dtype=np.float32)

    out_paths: list[Path] = []
    for i in range(N_LETTERS):
        start = i * samples_per_letter
        chunk = audio[start : start + samples_per_letter].copy()
        chunk = (chunk - float(np.mean(chunk))).astype(np.float32)
        peak = float(np.max(np.abs(chunk)))
        if peak > 0:
            chunk = (chunk / peak * PEAK_NORM).astype(np.float32)
        chunk[:fade_n] *= fade_in
        chunk[-fade_n:] *= fade_out
        letter = chr(ord("a") + i)
        out_path = out_dir / f"{letter}.wav"
        sf.write(out_path, chunk, sr, subtype="PCM_16")
        out_paths.append(out_path)
    print(
        f"[extract-bank] wrote {len(out_paths)} files to {out_dir}/ "
        f"({samples_per_letter} samples/letter @ {sr} Hz)"
    )
    return out_paths


def _print_bank_stats(out_paths: list[Path]) -> None:
    """Markdown table of per-letter peak/RMS/HF/DC stats.

    Copy-pasteable into ``spikes/02-synthesis-log.md`` so the baseline
    table regenerates whenever the bank does.
    """
    print()
    print("[extract-bank] per-letter stats:")
    print()
    print("| letter | peak  | RMS   | HF>5kHz | DC offset |")
    print("|--------|------:|------:|--------:|----------:|")
    for p in out_paths:
        audio, sr = sf.read(str(p), dtype="float32")
        spec = np.abs(np.fft.rfft(audio))
        freqs = np.fft.rfftfreq(audio.size, 1 / sr)
        hf = float(spec[freqs > 5000].sum() / (spec.sum() + 1e-12))
        peak = float(np.max(np.abs(audio)))
        rms = float(np.sqrt(np.mean(audio**2)))
        dc = float(np.mean(audio))
        print(
            f"| {p.stem:<6} | {peak:.3f} | {rms:.3f} "
            f"| {hf:.3f}   | {dc:+.4f}   |"
        )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Extract animalese A-Z letter bank into a directory."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("spikes/samples"),
        help="Directory to write {a..z}.wav into. Default: spikes/samples/",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help=(
            "Use a local pre-downloaded animalese.wav instead of fetching. "
            "Skips the download step (useful for offline / firewalled hosts)."
        ),
    )
    parser.add_argument(
        "--keep-source",
        action="store_true",
        help="Keep the downloaded source WAV after slicing (default: delete).",
    )
    args = parser.parse_args(argv)

    if args.source is not None:
        if not args.source.exists():
            print(f"ERROR: --source not found: {args.source}", file=sys.stderr)
            return 2
        source = args.source
        downloaded = False
    else:
        source = Path("/tmp/animalese-source.wav")
        download_source(source)
        downloaded = True

    out_paths = slice_letters(source, args.out)
    _print_bank_stats(out_paths)

    if downloaded and not args.keep_source:
        source.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
