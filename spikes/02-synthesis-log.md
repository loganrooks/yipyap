# Animalese static-mitigation log

Running notes on attempts to reduce audible static in Spike B animalese
output. One section per attempt. Append-only — don't edit verdicts after
the fact; if a follow-up changes the conclusion, add a new entry that
references the old one.

This file is **not** a general listening log. It exists to keep the
static-mitigation experiments separable so we can tell which change
actually moved the needle. Once `docs/listening-log.md` exists in Phase
1, the surviving conclusions get distilled there.

## Sources of static (working theory, 2026-05-16)

In rough order of suspected impact, before any fixes are tried:

1. Source `animalese.wav` ships as PCM_U8 (8-bit unsigned, ~48 dB
   intrinsic SNR). Quant hash is baked in before yipyap touches it.
2. `00_extract_bank.py` peak-normalizes each letter to 0.95 individually,
   amplifying the quant floor for naturally-quiet letters.
3. `02_synthesis.py:pitch_shift_from_to` uses `np.interp` linear
   resampling — no anti-aliasing on upward pitch shifts. At
   `--pitch-offset 12` (2× speed), 4–8 kHz folds back into 0–4 kHz.
4. DC offsets on a few letters (notably `f` at −0.143) introduce step
   discontinuities at placement boundaries that short edge fades only
   partially mask.
5. Linear crossfade in `render_word` is constant-amplitude, not
   constant-power — small modulation noise across the overlap region
   between adjacent letters in ASR mode.
6. Bank LPF in `load_samples_bank` is fixed at 4.5 kHz @ 16 kHz SR —
   too high to remove all quant hash, but lowering it kills fricative
   character (`s`, `f`, `t`, `x` identifying energy is in 4–8 kHz).

Entries below test these one at a time so the verdict is attributable.

## Per-letter baseline (2026-05-16, current `main`)

Stats from `spikes/samples/` after `00_extract_bank.py` runs against the
upstream `acedio/animalese.js` `animalese.wav`. All samples 44.1 kHz,
0.150 s, PCM_16, peak 0.95.

Top HF-energy offenders (fraction of spectral energy above 5 kHz):

| letter | HF ratio | RMS  | DC offset |
|--------|---------:|-----:|----------:|
| x      | 0.75     | 0.16 | −0.051    |
| s      | 0.74     | 0.26 | −0.066    |
| f      | 0.54     | 0.27 | **−0.143** |
| t      | 0.53     | 0.17 | −0.046    |
| z      | 0.35     | 0.25 | −0.048    |
| v      | 0.31     | 0.23 | −0.041    |
| y      | 0.31     | 0.27 | −0.024    |
| j      | 0.30     | 0.21 | −0.017    |

Typical non-fricative letter sits around HF ratio 0.10–0.20 and DC
offset within ±0.015. `f` is an outlier on DC offset by an order of
magnitude.

Listen verdict (1.0×): TODO — describe what static you hear and on
which letters / in which mode (cadence vs ASR vs mixed). Note clip(s)
used.

Listen verdict (0.75×): TODO.

## Attempts

### 0001 — DC-remove per letter at extract-time (plan E1a)

- **Date:** 2026-05-16
- **Status:** kept (correctness fix; Surface A verdict landed null
  on `f`; Surface B verdict superseded by the v2 pivot — see
  Decision below and findings 2026-05-16 (b)). Metadata reconciled
  2026-05-17 to drop the original "awaiting" framing; the entry
  itself was written pre-listen so the prediction text stays as-is
  (append-only discipline applies to predictions, not metadata).
- **Branch / commit:** Implemented on `phase-0/static-log-scaffold`
  atop the plan commit `4362754`; landed as `94d1662`.
- **Hypothesis:** Letters with measurable DC offset (`f` −0.143,
  `s` −0.066, `x` −0.051, `z` −0.048, `t` −0.046, `v` −0.041) place
  a non-zero start sample at each onset. The 5 ms linear fades at
  the cut edges (the 3 ms / 20 ms fades inside `apply_fades` apply
  later, at synthesis time) only partially mask this boundary step
  — especially for `f`, whose offset is an order of magnitude
  larger than typical. Removing per-letter DC at extract-time
  should eliminate the step at its source and let it propagate
  cleanly to both surfaces (A: `spikes/samples/{letter}.wav`; B:
  rendered output).
- **Change:** `spikes/00_extract_bank.py:slice_letters` — one new
  line, `chunk = (chunk - float(np.mean(chunk))).astype(np.float32)`,
  placed **before** peak-normalize (not after, despite the plan's
  E1a section saying "between peak-normalize and edge fades"; see
  `02-synthesis-findings.md` 2026-05-16 entry for why the order
  was switched). Module docstring updated to reflect the new step.
- **Measurements (before → after, on the regenerated bank, full
  letter set — `extract-bank` stats output 2026-05-16):**

  | letter | DC before | DC after  | peak before | peak after | HF before | HF after |
  |--------|----------:|----------:|------------:|-----------:|----------:|---------:|
  | a      | (≤0.005)  | +0.0000   | 0.950       | 0.950      | ~0.10     | 0.094    |
  | f      | **−0.1434** | +0.0019 | 0.950       | 0.950      | 0.54      | 0.556    |
  | s      | −0.0658   | −0.0020   | 0.950       | 0.950      | 0.74      | 0.749    |
  | t      | −0.0462   | +0.0016   | 0.950       | 0.950      | 0.53      | 0.540    |
  | v      | −0.0414   | +0.0005   | 0.950       | 0.950      | 0.31      | 0.313    |
  | x      | −0.0507   | +0.0001   | 0.950       | 0.950      | 0.75      | 0.758    |
  | z      | −0.0477   | +0.0007   | 0.950       | 0.950      | 0.35      | 0.355    |

  DC: original worst-offenders (f at −0.143) are reduced ~70×.
  Residual DC is tiny (≤ 0.002 in magnitude) and originates in the
  post-DC-subtract edge fades — not in the source bank. HF ratio:
  unchanged by construction (DC has no spectral content above DC).
  Peak: exactly 0.95 for every letter, including the high-DC ones
  that the literal plan order would have either clipped (z) or
  significantly dampened (f to 0.80, s to 0.88).
- **Listen verdict (Surface A, 1.0×, 2026-05-16, comparison
  via `spikes/samples-compare/f.wav` = baseline‖e1a):** **no
  audible difference on `f`** — both versions read as the same
  "static mess." See findings 2026-05-16 (b) for the reframe:
  DC offset wasn't `f`'s perceptual problem; edge fades already
  attenuated the boundary step. The change is real on paper
  (DC −0.143 → +0.002, peak now exactly 0.95, z no longer clips)
  but inaudible on Surface A for the worst-DC letter. Other
  worst-DC letters not yet listened to individually; predicted
  to be the same (the mid-letter noise dominates on all
  fricatives).
- **Listen verdict (Surface B, 1.0× / 0.75×):** not run.
  Superseded by the v2 pivot (see findings 2026-05-16 (c)).
  Original promise of "concatenated output could surface
  boundary-click reduction" stays here as historical record; the
  question stopped being load-bearing once cross-bank comparison
  showed bank source dominates the perceptual floor.
- **Decision:** **Keep (correctness).** Even without a perceptual
  win on Surface A, the change is a free correctness improvement
  — exact peak = 0.95 for every letter, no clipping on z, clean
  DC across the bank. Cost is one line. Carrying it forward into
  the E1b / E2 stack rather than reverting. Re-evaluate after
  Surface B listen + downstream experiments.

## Measurement cheatsheet

Per-letter stats — run after any change touching `00_extract_bank.py`
or the bank-loading path in `02_synthesis.py`:

```sh
python3 -c "
import soundfile as sf, numpy as np
from pathlib import Path
for p in sorted(Path('spikes/samples').glob('*.wav')):
    a, sr = sf.read(str(p), dtype='float32')
    spec = np.abs(np.fft.rfft(a))
    freqs = np.fft.rfftfreq(a.size, 1/sr)
    hf = spec[freqs > 5000].sum() / (spec.sum() + 1e-12)
    print(f'{p.stem}: peak={np.max(np.abs(a)):.3f} '
          f'rms={np.sqrt(np.mean(a**2)):.3f} '
          f'hf={hf:.3f} dc={np.mean(a):.4f}')
"
```

End-to-end synthesis (timbre test, no background, baseline pitch):

```sh
python spikes/02_synthesis.py \
  spikes/output/spike-a/<backend>-<model>/<clip>/voice.wav \
  --samples-dir spikes/samples/
# Listen to spikes/output/spike-b/spike-b-real.wav
```

End-to-end with ASR (the mode most prone to per-letter static because
the same letters fire predictably):

```sh
python spikes/02_synthesis.py \
  spikes/output/spike-a/<backend>-<model>/<clip>/voice.wav \
  spikes/output/spike-a/<backend>-<model>/<clip>/background.wav \
  --samples-dir spikes/samples/ --pitch-offset 12 \
  --asr-input spikes/inputs/<clip>.wav --asr-backend auto
# Listen to spike-b-asr.wav and spike-b-asr-mixed.wav
```
