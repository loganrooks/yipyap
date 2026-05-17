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

## 2026-05-16 (c) — The pivot: bank source is the floor

E1a's null result on Surface A was the first data point. The second
arrived from a different direction: a cross-bank A/B comparison
(acedio / equalo / DigiDuncan / joshxviii-f1) on the same Surface A
letters. **joshxviii-f1 sounded audibly cleaner by a wide margin
with zero pipeline change.** The user's verdict — "beyond the best" —
was unambiguous enough that no synthesis-side experiment needed to
intervene to confirm it.

The provenance check then established that this wasn't acedio
re-processed. `compare_josh_acedio.py` cross-correlated josh-f1's 26
letters against acedio's corresponding letters: mean xcorr 0.045, max
0.18 — same-recording correlation would land > 0.7. **josh-f1 is
definitively not acedio-derived.** This narrower claim is what the
script measures; the other seven josh voices (f2-f4, m1-m4) are
visibly distinct from each other and from f1 in the per-voice stats
(`josh_stats_full.txt` shows ~285 Hz f0 spread across the 8 voices),
but pairwise cross-correlation has only been computed for f1 vs
acedio — no within-josh xcorr matrix is committed. The architecture
decision to default to josh-f1 (not the multi-voice pool) is the one
this committed provenance check supports; any later move to multi-
voice (V2 of plan v2) needs either the pairwise matrix computed or
the within-josh distinctness argument grounded in per-voice f0/
spectrum stats rather than a cross-correlation result that hasn't
been measured.

The reframe — promoted to durable status here because two data points
agree: **the bank's quantization floor (PCM_U8 → ~48 dB SNR) is the
ceiling on any pipeline polish.** Everything v1 sequenced as E1–E5
(DC removal, loudness rebalance, LPF retune, anti-aliased resample,
constant-power crossfade) is cosmetic relative to that floor. The
v1 framing implicitly assumed acedio was workable substrate and the
synthesis pipeline was where the static came from. Neither
assumption survives the data: the substrate isn't workable, and the
pipeline isn't the bottleneck. The substrate is replaceable; that's
the lever.

What this changes:

1. **v1 plan is superseded but preserved** (`02-synthesis-plan.md`
   keeps its banner pointing here, but the rest is unchanged — the
   mismatch between v1's predictions and what we measured IS the
   learning signal, and editing the plan would destroy that).
2. **v2 plan exists** (`02-synthesis-plan-v2.md`) with new scope:
   V1 josh-f1 single-voice integration, V2 multi-voice mapping,
   V3 jitter port, V4 yelling-on-RMS, V5 cross-bank A/B at
   Surface C.
3. **E1a stays committed** because the correctness wins are real
   (peak exactly 0.95, no clipping on z, DC ≤ 2e−3) even though the
   perceptual win didn't materialise. The lesson — operation order
   matters for amplitude chains — generalises beyond this spike.
4. **The original "static-mitigation" framing dissolves.** Static is
   no longer the question once the bank is replaced; the questions
   become "which voice for which speaker," "how much jitter," "does
   yelling earn its keep." Surface C is added to formalise the
   listening surface where mapping decisions become attributable.

There's a sub-lesson here worth flagging for `docs/lessons.md` once
v2 V1 confirms the prediction transfers through synthesis: **when an
experiment line returns null on its first cheap test, before
spending more on the next, check whether the question itself is
still load-bearing.** The DC removal returning null didn't mean
"try harder DC fixes" — it meant "you're asking the wrong question
about where static comes from." The cross-bank listen was the test
that asked a different question entirely, and the answer reorganized
the whole plan.

This finding marks the end of the E1–E5 line of attack. Future
entries in `02-synthesis-log.md` should reference v2 venture numbers
(V0, V1, …), not v1 experiment numbers, except when explicitly
revisiting a v1 verdict.
