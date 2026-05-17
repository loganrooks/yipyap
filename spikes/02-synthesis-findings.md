# Spike B — synthesis findings

Free-form qualitative notes on what static-mitigation work on
`02_synthesis.py` has actually taught us. **Not** a per-attempt log —
that's `02-synthesis-log.md`. This file is where the lab notebook gets
read back and digested.

Conventions:

- Add free-form sections as understanding evolves. Date each section
  so the timeline stays readable.
- Don't delete an old section when a later one contradicts it. Write a
  new section that explains the shift, so the reader can see how the
  understanding moved.
- When a finding here generalises beyond Phase 0, distill it into
  `docs/lessons.md` and link back here.

## 2026-05-16 — Operation order matters: DC removal must precede peak-norm

The plan's E1a section ("Per-letter DC removal at extract-time") said
to do DC removal *between* peak-normalize and edge fades. The literal
implementation of that order — peak-norm to 0.95, then subtract
per-letter DC — caused a regression on one letter:

- `z` post-pipeline peak = 0.999969 (PCM_16 ceiling = 0.99997). z had
  a positive DC bias post-peak-norm and a significant negative-side
  envelope, so DC subtraction pushed the negative peak past −1.0 and
  it saturated on PCM_16 write.
- Other DC-affected letters had peak *drop* (f 0.95 → 0.80, s 0.95
  → 0.88, t → 0.90, x → 0.90), trading one boundary problem (DC
  step) for another (lost headroom / per-letter loudness imbalance).

Re-ordering to **DC remove → peak-norm → edge fades** sidesteps both:
peak-norm operates on a zero-mean signal, so post-norm peak is
exactly 0.95 for every letter and no clipping is possible. The DC
goal is preserved (still zero-mean before fades; fades introduce a
tiny residual on the order of 1e−3, two orders of magnitude smaller
than the original DC offsets).

The lesson generalizes: **when chaining amplitude operations, DC
adjustments should precede gain adjustments** — otherwise you're
amplitude-normalising the wrong reference signal and the bias rides
through every downstream step asymmetrically. Filed into
`docs/lessons.md` as L002 (after E1a has a listen verdict, so it
graduates with a verified outcome, not just a theoretical prediction).

The E1a section of the plan has not been edited to match — the plan
is a frozen prediction, not a moving target. The mismatch *is* the
learning signal.

## 2026-05-16 (b) — DC offset isn't the perceptual problem on fricatives

E1a's Surface A listen on `f` returned **no audible difference**
against baseline. Predicted: "f sounds less thumpy at start/end."
Reality: indistinguishable static mess on both.

The reframe: **on this bank, DC offset is a correctness concern,
not a perception concern.** The chain is:

1. The DC step exists at the raw cut edge (e.g. `f` raw sample at
   index 0 was ~−0.143).
2. But the extract-time edge fade (`FADE_S = 0.005 s`, linear)
   already attenuates the cut edge to near-zero amplitude before
   the user ever hears it. The DC value at the fade-zero point is
   `−0.143 × 0 = 0`. So the *audible* boundary discontinuity was
   already mostly masked by the fade-in / fade-out we inherit.
3. What the listener hears as "static mess" on `f` is **mid-letter
   content**: the PCM_U8 quantization hash (~48 dB intrinsic SNR,
   amplified by per-letter peak-norm on quiet letters) plus the
   inherent broadband noise of the /f/ fricative phoneme itself.
   Neither lives anywhere near DC. Subtracting the DC component
   removes nothing perceptually relevant.

This doesn't mean E1a is worthless — the change still cleans up DC,
sets exact peak = 0.95 across the bank, and removes the clipping
risk on `z` that Order A had. Those are real correctness wins. But
**the case for E1a as a static-mitigation experiment, on Surface A,
is closed: it doesn't help.**

There's still a path where E1a pays off: **Surface B in ASR mode.**
When many `f` letters fire close together in rendered output, their
start/end edges *do* aggregate, and small per-edge effects that are
inaudible in isolation could become audible in sum. That test hasn't
been run; until it has, E1a's stitched-output claim is open. But the
isolated-letter case is decided.

The broader generalizable lesson — to graduate into
`docs/lessons.md` after at least one more experiment confirms the
pattern: **on heavily-quantized short samples, perceptual static is
dominated by mid-letter quant hash and phoneme-intrinsic noise,
not by boundary discontinuities the edge fades already mask.** The
implication for sequencing future experiments: cheap-but-cosmetic
fixes (DC, peak-norm hygiene) should be deprioritized vs.
floor-lifting fixes (dither / re-quantize, anti-alias resample,
re-source bank) when the perceptual rubric is "does it sound less
staticky."
