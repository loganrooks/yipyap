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

### Template (copy for each new attempt)

#### NNNN — short-name

- **Date:**
- **Status:** tried | kept | reverted
- **Branch / commit:** sha or `uncommitted`
- **Hypothesis:** why we expect this change to reduce static
- **Change:** plain-English description of the diff (file + function)
- **Measurements (before → after):** HF ratio / RMS / DC offset on the
  letters this is supposed to affect; or end-to-end SNR if relevant
- **Listen verdict (1.0× / 0.75×):** human ear, required before
  `kept` / `reverted`. Note clip, bank, pitch-offset, mode (cadence /
  ASR / mixed). Compare against baseline listen on the same clip.
- **Decision:** what we learned + next pointer

(Delete this template once the first real attempt is appended.)

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
