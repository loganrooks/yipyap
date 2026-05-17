# Spike B — synthesis static-mitigation plan

> Sub-plan within `docs/spike-plan.md` Spike B. Coordinates the
> structured investigation into reducing audible static in animalese
> output. Companion docs: `02-synthesis-log.md` (per-attempt data),
> `02-synthesis-findings.md` (qualitative reflections),
> `../docs/lessons.md` (cross-venture durable takeaways).

## Purpose

Some of the audible static in animalese is **intrinsic** to the bank
we extract (see L001 in `docs/lessons.md`); some is **created** by the
synthesis pipeline. This plan sequences experiments that disambiguate
the two, with predictions written down before measurement so we learn
when reality disagrees.

Goal: a **kept stack** — the combination of fixes that produces the
best output under production constraints — written into
`docs/lessons.md` at the end as the recommendation that crosses into
Phase 1.

## Listening surfaces

Two distinct surfaces. **Each fix is only audible on the surface where
it lives.**

| Surface | Path                                                | What it captures                                                |
|---------|-----------------------------------------------------|------------------------------------------------------------------|
| **A**   | `spikes/samples/{a..z}.wav`                         | Intrinsic per-letter timbre, baked-in hash, character.           |
| **B**   | `spikes/output/spike-b/spike-b-{cadence,real,asr}.wav` | Pipeline-amplified artifacts (aliasing, crossfade, placement). |

Fix-point convention — three options:

- **Extract-time** (`spikes/00_extract_bank.py`): rewrites the on-disk
  bank. Surface (A) audits the fix; (B) inherits it via load.
- **Load-time** (`02_synthesis.py:load_samples_bank`): bank touched in
  memory only. Surface (A) unchanged; (B) reflects fix.
- **Render-time** (`02_synthesis.py:render_word` / placement /
  pitch-shift): (A) unchanged; (B) reflects fix.

**Rule:** if a fix is conceptually about the *bank*, put it at
extract-time so (A) audits it. If a fix is about the *pipeline*,
leave it at load- or render-time. The earlier work in attempt 0001
(see `02-synthesis-log.md`) violated this rule — it lives at load-time
but is a bank fix. It will be moved to extract-time per E1a before
the listen verdict is recorded.

## Variables tracked

### Quality (per fix)

**Per-letter (surface A), objective** — regenerable from
`00_extract_bank.py`'s stats dump:

| Metric             | Definition                                            |
|--------------------|-------------------------------------------------------|
| DC offset          | `np.mean(s)`                                          |
| Peak               | `np.max(np.abs(s))`                                   |
| RMS                | `sqrt(np.mean(s**2))`                                 |
| HF ratio           | `sum(\|FFT\|[f>5kHz]) / sum(\|FFT\|)`                 |
| Spectral flatness  | `geomean(spec) / arithmean(spec)` (0=tonal, 1=noisy)  |

Spectral flatness is new (added in E2) — distinguishes tonal hash
(low flatness) from broadband hiss (high flatness) at the same total
energy, which the HF ratio alone collapses.

**Per-letter (surface A), subjective** — 1–5, listen per letter:

| Dimension     | 1 (worst)                              | 5 (best)                                |
|---------------|----------------------------------------|------------------------------------------|
| static        | Distractingly hash-y; can't ignore     | No audible static                        |
| character     | Consonant identity lost                | Full consonant identity intact           |
| naturalness   | Sounds broken / artifacted             | Sounds like clean animalese letter       |

**End-to-end (surface B), objective:**

| Metric              | Definition                                                  |
|---------------------|--------------------------------------------------------------|
| Output peak         | post-normalize peak (sanity)                                |
| Aliasing residue    | RMS of `up(s) - up(down(up(s)))` (relevant for E4)          |
| Boundary-click amp  | peak amplitude in ±10ms window around letter joins (ASR mode)|

**End-to-end (surface B), subjective** — 1–5, listen end-to-end at
1.0× then 0.75×:

| Dimension     | 1                                       | 5                                      |
|---------------|-----------------------------------------|----------------------------------------|
| static        | Distractingly static-y                  | No audible static                      |
| cadence       | Rhythm wrong / slips audibly            | Rhythm tracks commentary               |
| naturalness   | Doesn't sound like animalese over sport | Sounds like AC animalese over sport    |

0.75× exposes alignment slips that mask at full speed.

### Production at scale (feasibility)

Recorded per fix:

| Variable           | What we record                                                | Why it matters                              |
|--------------------|---------------------------------------------------------------|---------------------------------------------|
| Extract cost       | wall-clock seconds for `00_extract_bank.py` re-run            | Cheap regen = fast iteration                |
| Synthesis RTF      | `wall_clock / clip_duration` on the test fixture              | Real-time-factor target for batch deploy    |
| New deps           | pip packages added vs `spikes/requirements.txt`               | Each dep is a lifetime maintenance cost     |
| Code complexity    | net lines added; new functions; branching depth                | Maintainability + cognitive load            |
| Memory             | peak Python RSS on synth of a 30s clip                         | Batch processing of long broadcasts         |
| Determinism        | same input → same output bit-exact? (md5 of result)            | Reproducibility, debuggability              |
| Configurability    | hardcoded / CLI flag / auto                                    | UX for downstream users (Phase 1)           |

**Action item before E1a runs:** establish baseline extract-bank
wall-clock and synth RTF on the fixture clip, recorded in the log's
baseline section. Deltas are only attributable if the starting point
is captured.

## Experimental design principles

1. **One variable at a time.** Combine only in the hybrid step.
2. **Same clip family throughout.** Cross-clip drift confounds.
3. **Predict before measuring.** Each experiment has predicted quant
   deltas + predicted qual verdict written *before* the listen.
   Prediction-vs-reality mismatches are the most informative outcome.
4. **Sequence by Pareto efficiency.** Cheap-and-promising first.
5. **Reversibility.** Each fix lives behind a clean diff. Reverting
   a non-winner doesn't disturb the rest.
6. **Stopping criteria, written down.** See bottom of doc.

## Test fixture

(User: confirm or override.)

- Source clip: `spikes/inputs/abu_dhabi_60-90.wav`
- Voice stem: `spikes/output/spike-a/mdx-UVR-MDX-NET-Inst_HQ_3/abu_dhabi_60-90/voice.wav`
- Background stem: `spikes/output/spike-a/mdx-UVR-MDX-NET-Inst_HQ_3/abu_dhabi_60-90/background.wav`
- Pitch offset (surface-B renders): `+6` (per README's canonical
  invocation). Spot-check at `+12` for any pitch-shift experiment (E4).
- Mode focus: ASR (problem letters fire predictably → attribution easier).

## Baseline (E0)

Captured in `02-synthesis-log.md` "Per-letter baseline" section.
Headline:

- Top HF ratios: x 0.75, s 0.74, f 0.54, t 0.53.
- Worst DC: f −0.143 (10× typical).
- Bank LPF cutoff: 4.5 kHz @ 16 kHz SR.
- Source: PCM_U8 → ~48 dB SNR.

**Surface A subjective baseline:** TBD — listen letter-by-letter to
`spikes/samples/{a..z}.wav` and record per-letter scores in the log
before any fix lands.

**Surface B subjective baseline:** TBD — render the fixture clip in
cadence / timbre / ASR modes (per the README invocations) and score.

**Cost baseline:** TBD — `time python spikes/00_extract_bank.py` and
`time python spikes/02_synthesis.py …` on the fixture.

## Experiments

### E1 — DC handling

#### E1a — Per-letter DC removal at extract-time

**Where:** `spikes/00_extract_bank.py:slice_letters`, between
peak-normalize and edge fades.

> *Implementation note (2026-05-17):* The actual extraction subtracts
> DC *before* peak-normalize, not between peak-normalize and fades.
> The literal plan order clipped `z` at the PCM_16 ceiling — see
> findings 2026-05-16 (a) for the recorded mismatch and operation-
> order lesson. **This prediction is preserved unchanged** per the
> banner at the top of this file: the mismatch between prediction
> and implementation IS the learning signal, and rewriting the
> prediction would erase it. Read this section as the original plan,
> not the current implementation.

**Hypothesis:** Per-letter DC offset (f −0.143, s −0.066, x −0.051,
z −0.048, t −0.046, v −0.041) places a non-zero sample at every
letter start/end. The 3 ms fade-in / 20 ms fade-out only partially
mask this. Subtracting per-letter mean before fades eliminates the
boundary step at the source.

**Surfaces:** A (primary), B (inherits).

**Measured + predicted:**

| Metric                       | Pre        | Predicted post   |
|------------------------------|-----------:|------------------:|
| DC offset (f)                | −0.143     | < 1e−6            |
| DC offset (s)                | −0.066     | < 1e−6            |
| HF ratio (any)               | (baseline) | unchanged         |
| Peak (any)                   | 0.95       | 0.95              |
| static rating (A, f)         | TBD        | +1–2 points       |
| static rating (A, others)    | TBD        | ±0                |
| boundary-click amp (B, ASR)  | TBD        | drops noticeably  |
| static rating (B, ASR)       | TBD        | +0–1 point        |

**Qual predictions:**

- (A) `f` sounds less "thumpy" at start/end; minor improvement on
  other DC-affected letters; rest indistinguishable.
- (B) Boundary clicks at f/s/t/x placements reduce, biggest in ASR
  mode where the same problem letters recur predictably.
- Does NOT touch mid-letter hash (that's E2).

**Production cost:** Trivial. ~3 lines. No new deps. Extract-bank
wall-clock change negligible (<1%). Determinism preserved.

**Risk:** ~none.

**Status:** Attempt 0001 in the log is the load-time version. Needs to
move to extract-time per the surface convention before the listen.

#### E1b — Bank-wide loudness normalization

**Where:** `slice_letters`. Replace per-chunk peak-norm with
two-pass: find bank-max peak, normalize all letters to that max.

**Hypothesis:** Current per-letter peak-norm to 0.95 amplifies the
quant-noise floor on naturally-quiet letters (e.g. `p` RMS 0.150 →
implied ~5× scale-up of any noise). Bank-wide peak-norm preserves
natural per-letter loudness and lowers noise scaling for quiet letters.

**Surfaces:** A (primary), B (inherits).

**Measured + predicted:**

| Metric                | Pre        | Predicted post     |
|-----------------------|-----------:|-------------------:|
| Peak (per letter)     | all = 0.95 | max=0.95, others < |
| RMS spread            | 0.15–0.34  | wider, ~0.05–0.34  |
| HF ratio (quiet ones) | (baseline) | drops noticeably   |

**Qual predictions:**

- (A) Quiet letters (p, k, w, x) sound markedly cleaner; loud
  letters unchanged.
- (B) Cadence rhythm may sound less even (quiet letters now actually
  quiet). Could be a feature (more natural) or a bug (less rhythmic
  punch) — listen carefully in cadence mode.

**Production cost:** Trivial. ~5 lines. No new deps.

**Risk:** Output rhythm character changes. If we don't like that,
need render-time envelope balance (E6).

### E2 — Re-quantization with dither

**Where:** `slice_letters`, before `sf.write` (after E1 if kept).

**Hypothesis:** Source is PCM_U8 (256 levels). Current PCM_16 write
preserves U8 quant peaks as 16-bit silence + tonal hash. Adding
triangular-PDF dither at 1-LSB amplitude (at the U8 quantum scale)
before requantizing whitens the hash — converts tonal artifacts into
broadband noise that's psychoacoustically less salient at the same
energy.

**Surfaces:** A (primary), B (inherits).

**Measured + predicted:**

| Metric                  | Pre        | Predicted post              |
|-------------------------|-----------:|----------------------------:|
| HF ratio                | (baseline) | small increase              |
| Spectral flatness       | low (tonal)| markedly higher (noisy)     |
| RMS                     | (baseline) | trivial increase            |

**Qual predictions:**

- (A) Static doesn't go away — it *changes character* from tonal
  hash to tape-hiss. Subjectively less annoying for the same
  measurable energy.
- (B) Improvement most audible when many letters overlap (ASR mode).

**Production cost:** ~5 lines. No new deps (numpy random).

**Risk:** Wrong dither PDF or amplitude makes things worse. Stick
to triangular PDF, 1-LSB amplitude.

### E3 — Bank LPF tuning

**Where:** `02_synthesis.py:load_samples_bank` (load-time keeps the
sweep cheap — no bank regenerate per iteration).

**Hypothesis:** Fixed 4.5 kHz LPF attenuates 4.5–8 kHz hash but also
dulls fricative identifying energy (which lives in 4–8 kHz). Three
variants to disentangle:

- **E3a:** brick-wall cutoff sweep at 3.5 / 5.5 / 6.5 kHz.
- **E3b:** high-shelf attenuation (e.g. −6 dB above 4 kHz) instead
  of brick-wall.
- **E3c:** per-letter LPF — apply only to non-fricatives;
  leave s/f/t/x unfiltered.

**Surfaces:** B primary. (A audit only if we add a `--bake-bank`
flag to write the load-time pipeline back to disk.)

**Measured + predicted:**

| Variant      | HF ratio (s,x,f)   | Character (A)        | Static (A)         |
|--------------|--------------------|----------------------|--------------------|
| 3.5 kHz      | sharply lower      | drops 1–2 points     | rises 1 point      |
| 5.5 kHz      | slightly lower     | ~unchanged           | small improvement  |
| 6.5 kHz      | barely lower       | unchanged            | minimal            |
| Shelf −6 dB  | moderately lower   | small drop           | moderate           |
| Per-letter   | targeted           | unchanged            | targeted           |

**Qual predictions:**

- 3.5 kHz: clearly less hash, but `s` sounds like `sh`, `f` like
  `h`. Not worth it.
- 5.5 kHz: small win both axes. Probable keeper.
- Shelf: preserves character better than brick-wall at same hash
  reduction. Likely best simple variant.
- Per-letter: best targeted result, more code complexity.

**Production cost:** Trivial for E3a/E3b. Moderate for E3c.

**Risk:** Aggressive cutoff = lost consonant character. The
character rubric catches it.

### E4 — Anti-aliased pitch shift

**Where:** `02_synthesis.py:pitch_shift_from_to`.

#### E4a — Polyphase resample (`scipy.signal.resample_poly`)

**Hypothesis:** Current `np.interp` linear resampling has no
anti-aliasing. At `--pitch-offset 12` (2× speed), 4–8 kHz folds back
into 0–4 kHz as audible aliasing. Polyphase resampling applies a
low-pass during resample.

**Surfaces:** B only.

**Measured + predicted:**

| Pitch offset | Aliasing residue (pre) | (post)   | Static B rating (post) |
|--------------|-----------------------:|----------:|------------------------:|
| 0            | none                   | none      | unchanged               |
| +6           | moderate               | low       | +0–1 point              |
| +12          | high                   | very low  | +1–2 points             |

Wall-clock per shift call: 5–15× slower than `np.interp`. Still
< 1 ms per call; negligible for offline batch.

**Qual predictions:**

- (B, +12) Big improvement. "Crispy" HF garbage gone.
- (B, +6) Moderate. Noticeable but not dramatic.
- (B, 0) No change.

**Production cost:** ~3 lines (replace `np.interp` call). scipy
already a dep.

**Risk:** Mild HF dulling from polyphase LP. Listen with character
rubric.

#### E4b — Pre-LPF based on shift ratio

**Hypothesis:** Cheap proxy for E4a — low-pass the sample to
`Nyquist / ratio` before resampling. Removes content that would
alias without invoking polyphase machinery.

**Predicted:** similar quality to E4a; lower wall-clock overhead;
may leave residue at sharp transients.

**Run only if E4a is too slow for the production target.**

### E5 — Equal-power crossfade

**Where:** `02_synthesis.py:render_word`. Replace linear fade halves
with `sqrt` fade halves so overlapping letters sum to constant power
across the overlap region.

**Hypothesis:** Linear crossfade is constant-amplitude
(`sum = const`), not constant-power (`sum² ≠ const`). With
uncorrelated phase between adjacent letters, perceived amplitude
dips ~3 dB at the midpoint of the overlap, producing small
modulation noise audible in ASR mode.

**Surfaces:** B only.

**Measured + predicted:**

- Per-letter peak: unchanged.
- Static rating (B, ASR): +0–1 point. Marginal but cheap.

**Qual predictions:** Subtle improvement; audible on careful
back-to-back A/B comparison. Worth keeping if free; not a
make-or-break.

**Production cost:** Trivial. `np.linspace` → `np.sqrt(np.linspace)`.

**Risk:** None.

### E6 — Loudness balance compensation

**Only run if E1b reveals a rhythm-punch problem.** Render-time
gain-up of quiet letters to restore cadence. Not a static fix per
se — a compensation. Deferred until E1b's verdict.

### E7 — Re-source the bank

**Where:** `00_extract_bank.py:download_source` and beyond.

**Hypothesis:** The animalese.js bank's PCM_U8 source is the limiting
factor. A higher-fidelity source (16-bit re-extraction, or fresh
sample recording) eliminates the entire intrinsic-hash class of static.

**Surfaces:** A (massive), B (inherits).

**Measured + predicted:**

- HF ratio on fricatives: depends entirely on source.
- Determinism / reproducibility: depends on source being publicly
  re-extractable.
- Spectral flatness in noise floor: higher (less tonal).

**Qual predictions:** Could eliminate the intrinsic-static class
entirely. Could also lose the AC aesthetic — the lo-fi character is
*part* of the charm. Major design judgment call.

**Production cost:** Significant. Manual sample work; source must be
documented + redistributable / re-extractable.

**Risk:** Highest of any experiment. AC aesthetic loss; legal
redistribution; reproducibility for future maintainers.

### E_hybrid — Winning stack

After E1–E5 (+ E6 if needed) have individual verdicts:

1. Apply all `kept` fixes in their natural pipeline order
   (extract-time first, then load-time, then render-time).
2. Regenerate bank + render reference clip.
3. Measure surface A + B (objective + subjective).
4. **Compare the stack to the sum of its parts:**
   - Constructive (stack > sum): fixes combine well. Confirm + ship.
   - Subtractive (stack < sum): some fix is redundant or harmful in
     combo. Drop the weakest. Re-measure.
   - Cancelling (stack ≈ baseline): something is wrong.
     Investigate before continuing.

The final stack and its rationale land in `docs/lessons.md` as a
new lesson (L00n) with the knob configuration Phase 1 inherits.

## Sequencing

Ordered by `quick_to_run × likely_impact / risk`:

1. **E1a** — DC remove at extract-time. Trivial, near-zero risk,
   targets the worst objective outlier (f). Lets surface (A)
   audits begin.
2. **E1b** — Bank-wide normalize. Trivial; biggest potential win on
   quiet-letter hash.
3. **E2** — Dither. Cheap; well-understood psychoacoustic win.
4. **E5** — Equal-power crossfade. Trivial; sanity-checks an
   assumption.
5. **E4a** — Polyphase pitch shift. Moderate cost; biggest perceptual
   win at high `--pitch-offset`. Skip E4b unless E4a is too slow.
6. **E3** — LPF tuning. Cheap but tradeoff-laden; run after E1/E2
   so the LPF's job is just hash management, not DC fix too.
7. **E_hybrid** — Stack the winners. Measure interactions.
8. **E7** — Re-source. Only if E1–E5 + E_hybrid still insufficient.

## Stopping criteria

Stop iterating when **all** of:

- (A) On worst 6 letters (f/s/x/t/z/v): static ≥ 3 AND character ≥ 3.
- (B) ASR + bg combined render: static ≥ 3 AND cadence ≥ 3.
- No single-experiment delta exceeds the noise floor of subjective
  listening (we can't reliably tell pre from post).

When met → distill into `docs/lessons.md`; freeze the synthesis
pipeline configuration for Phase 1.

When NOT met after E1–E5 + E_hybrid → seriously consider E7.

## Learning from prediction-vs-reality mismatches

Every entry in `02-synthesis-log.md` ends with a Decision field.
When predicted ≠ observed, **write the why in
`02-synthesis-findings.md`**, not in the log:

- Was the *measurement* wrong (instrument / metric not capturing
  what we thought)?
- Was the *listening method* wrong (wrong surface, mode, or clip)?
- Was the *model of the artifact* wrong (e.g. it wasn't DC after
  all)?
- Did we under- or over-estimate the effect size?
- What new experiment does this suggest?

Pattern recognition across mismatches gets distilled into
`docs/lessons.md` as Phase-independent insights.

## Open questions / decisions to make

- **Test clip:** confirm `abu_dhabi_60-90` or pick a canonical
  alternative. Whichever, fix it for the run of experiments.
- **`--bake-bank` debug flag:** add to `02_synthesis.py` so load-time
  fixes can be written back to disk for surface (A) audit? Worth it
  if E3 (LPF tuning, load-time) needs A-level evaluation.
- **Automated subjective scoring:** PESQ / mel-spec / neural
  perceptual loss could lower listening burden if experiment count
  grows. Probably out of scope for Phase 0; flag if it becomes a
  bottleneck.
- **Source diversity:** the upstream `animalese.js` bank is one
  voice. Should Phase 1 support alternative banks? Affects E7's
  weight.

## Update log

- 2026-05-16 — initial plan written. Baseline E0 in log; attempt
  0001 in flight at load-time (needs revision per E1a fix-point rule).
- 2026-05-17 — **superseded.** See top-of-file banner and
  `02-synthesis-plan-v2.md` (on PR #9 / `phase-0/bank-pivot`). The
  "in flight" status above stayed deliberately frozen as the original
  pre-listen claim; the actual outcome is recorded in
  `02-synthesis-log.md` entry 0001 (committed at `94d1662` after
  Surface A listen, Surface B superseded by the v2 pivot).
