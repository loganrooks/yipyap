# Spike B — synthesis plan v2 (bank integration + multi-voice)

> Supersedes `02-synthesis-plan.md` (v1) on 2026-05-16. Same discipline
> (variables, predictions, sequencing, stopping criteria); different
> scope. Companion docs unchanged: `02-synthesis-log.md` (per-attempt
> data, append-only), `02-synthesis-findings.md` (qualitative
> reflections, append-only), `02-synthesis-research.md` +
> `02-synthesis-research-josh.md` (the inputs that drove the pivot),
> `../docs/lessons.md` (cross-venture durable takeaways).

## What changed and why

v1 sequenced E1–E5 inside the pipeline: DC removal, loudness rebalance,
LPF retune, anti-aliased pitch shift, constant-power crossfade. The
implicit assumption was that the acedio bank was a workable substrate
and the static came from how we *handled* it.

Two measurements killed that assumption:

1. **E1a returned null on Surface A.** DC cleanup made the bank
   measurably correct (peak exactly 0.95, z no longer clips, DC ≤ 2e−3
   everywhere) but produced **no audible difference** on `f` —
   findings 2026-05-16 (b). The static people hear is mid-letter PCM_U8
   quant hash plus intrinsic fricative noise, neither of which lives
   anywhere near DC.
2. **Cross-bank A/B was decisive.** Same Surface A letters, four banks
   (acedio / equalo / DigiDuncan / joshxviii-f1): joshxviii-f1 was
   audibly cleaner by a wide margin with zero pipeline change.
   Provenance check (`compare_josh_acedio.py`, 28 cross-correlation
   pairs, mean xcorr 0.045) confirms it's independent 16-bit material,
   not a re-processed acedio rip.

The reframe: **the bank's quantization floor (PCM_U8 → ~48 dB SNR) is
the ceiling on any pipeline polish.** v1's E1–E5 are cosmetic fixes on
a floor we can replace outright. v2's scope is replacing the floor and
making good on what joshxviii's source gives us — eight independently-
recorded voices, room for per-speaker assignment, headroom for
modulation.

Findings entry (c) captures the pivot in prose; this plan captures it
as an executable sequence.

## What's in scope for v2

- **V1.** Single-voice integration: drop `samples-josh-f1/` into the
  existing `--samples-dir` plumbing and run end-to-end on the F1
  fixture. No pipeline code change.
- **V2.** Multi-voice mapping: map diarized speakers → voice bank by
  pitch ordinal + curated pool, with per-speaker override.
- **V3.** Per-letter pitch jitter port from josh (`audio-manager.cjs`
  pattern, ~5 LOC in `render_word`).
- **V4.** Yelling-on-RMS: route loud onsets to a yelling render
  (pitch + jitter + volume composite). Optional; depends on V1 ceiling.
- **V5.** Cross-bank A/B in stitched output — formalise Surface C as a
  durable listening surface.

## What's out of scope for v2

- Recording an original bank. User explicitly: "I am not recording
  anything." Removed from sequencing.
- Re-quantize / dither work on the acedio bank (v1 E2). The acedio bank
  is no longer the carrier; raising its floor is fixing the wrong
  thing.
- Anti-aliased pitch shift via `resample_poly` (v1 E4). Worth
  revisiting only if V3's jitter exposes audible aliasing at the new
  pitch range — predict not, since josh-f1 doesn't and runs the same
  formula. Park; revisit only if V3 listen says otherwise.
- Render-time crossfade rebalance (v1 E5). Park behind V1 — the
  current crossfade has not been blamed by ear once the bank changes.
- IP / legal questions about josh's bank provenance. Out of scope for
  a private CLI per user direction.

## Listening surfaces

A third surface is introduced; A and B are unchanged from v1.

| Surface | Path                                                        | What it captures                                             |
|---------|-------------------------------------------------------------|--------------------------------------------------------------|
| **A**   | `spikes/samples-<bank>/{a..z}.wav`                          | Intrinsic per-letter timbre, baked-in hash, character.        |
| **B**   | `spikes/output/spike-b/<bank>-<mode>.wav`                   | Single-voice pipeline output. Pipeline artifacts attributable.|
| **C**   | `spikes/output/spike-b/multi-<map>.wav`                     | Multi-voice end-to-end mix. Mapping artifacts attributable.   |

**Naming convention:** Surface A / B / C output files are named so the
listen log entry is unambiguous about which bank, which mode, which
mapping. Example: `spike-b-josh-f1-asr.wav`, `multi-pitchordinal-f1.wav`.

**Rule (unchanged from v1):** if a fix is conceptually about the *bank*,
extract-time. If it's about the *pipeline*, load- or render-time. The
new rule for v2: if a fix is conceptually about *speaker→voice mapping*,
it lives at synthesis-front-matter (a new layer between diarization and
`render_word`).

## Variables tracked

### Per-bank, per-voice (Surface A)

Objective — regenerable from `stats_josh.py` style scripts (one per
bank):

| Metric             | Definition                                            |
|--------------------|-------------------------------------------------------|
| DC offset          | `np.mean(s)` per letter                               |
| Peak               | `np.max(np.abs(s))` per letter                        |
| RMS                | `sqrt(np.mean(s**2))` per letter                      |
| HF ratio           | `sum(\|FFT\|[f>5kHz]) / sum(\|FFT\|)` per letter      |
| Spectral flatness  | tonal vs broadband at fixed energy                    |
| f0 (voice mean)    | `librosa.pyin` median over voiced letters             |
| f0 spread          | IQR of per-letter pyin medians                        |

Subjective (1–5, per letter, then per voice as roll-up):

| Dimension     | 1 (worst)                              | 5 (best)                                |
|---------------|----------------------------------------|------------------------------------------|
| static        | Distractingly hash-y                   | No audible static                        |
| character     | Consonant identity lost                | Full consonant identity intact           |
| voice id      | Indistinguishable from others in bank  | Clearly distinct timbre                  |

### End-to-end (Surface B/C)

Objective:

| Metric              | Definition                                                  |
|---------------------|-------------------------------------------------------------|
| Output peak         | post-normalize peak (sanity)                                |
| Mapping consistency | same speaker → same voice across clip (no oscillation)      |
| Voice-switch density| voice transitions per minute (sanity: not seizure-rate)     |

Subjective (1–5, listen at 1.0× then 0.75×):

| Dimension     | 1                                       | 5                                      |
|---------------|-----------------------------------------|----------------------------------------|
| static        | Distractingly static-y                  | No audible static                      |
| cadence       | Rhythm wrong / slips audibly            | Rhythm tracks commentary               |
| naturalness   | Doesn't sound like animalese over sport | Sounds like AC animalese over sport    |
| speaker id    | Can't tell who's talking                | Each commentator distinguishable       |
| variety       | Monotonous; same voice fatigues         | Multi-voice feels alive                |

`speaker id` and `variety` are new in v2 — they're what multi-voice
buys us, and they have to be scored explicitly or the mapping work
goes unmeasured.

### Production at scale (feasibility)

Same dimensions as v1, plus two new ones for v2:

| Variable           | What we record                                                | Why it matters                              |
|--------------------|---------------------------------------------------------------|---------------------------------------------|
| Extract cost       | wall-clock for re-extracting a new bank (e.g. josh-f3)        | Adding a voice should be cheap              |
| Synthesis RTF      | `wall_clock / clip_duration` on the fixture                   | Multi-voice can't tank RTF                  |
| New deps           | pip packages added vs `spikes/requirements.txt`               | Each dep is a lifetime cost                 |
| Code complexity    | net lines added; mapping layer LOC                            | Maintainability                             |
| Memory             | peak Python RSS — multi-voice loads N banks                    | 8× banks at 1 MB each = small but check     |
| Determinism        | same input → same output bit-exact? (md5)                     | Reproducibility                             |
| Configurability    | hardcoded / CLI flag / override file                          | UX for downstream users                     |
| **Bank disk cost** | bytes per bank × number of banks shipped                       | New in v2 — multi-voice multiplies storage  |
| **Mapping audibility** | listener can tell mapping mode changed without being told  | New in v2 — V2 only earns its keep if yes   |

## Experimental design principles (unchanged from v1)

1. **One variable at a time.** Combine only in V5.
2. **Same clip family throughout.** Cross-clip drift confounds.
3. **Predict before measuring.** Every venture has predicted quant
   deltas + predicted qual verdict written *before* the listen.
4. **Sequence by Pareto efficiency.** Cheapest-and-most-informative first.
5. **Reversibility.** Each venture lives behind a clean diff.
6. **Stopping criteria, written down.** See bottom of doc.

## Test fixture (unchanged from v1)

- Source clip: `spikes/inputs/abu_dhabi_60-90.wav`
- Voice stem: `spikes/output/spike-a/mdx-UVR-MDX-NET-Inst_HQ_3/abu_dhabi_60-90/voice.wav`
- Background stem: `spikes/output/spike-a/mdx-UVR-MDX-NET-Inst_HQ_3/abu_dhabi_60-90/background.wav`
- Pitch offset (Surface B): `+6`. Spot-check `+0` once on josh-f1 since
  josh's f0 is already ~396 Hz (vs acedio's bank meant for +6 lift).
- Mode focus: **ASR** for V1/V2/V3 (problem letters fire predictably;
  speaker turns clear); **cadence** for V4 spot-check.

## Baseline (V0)

Two baselines required before any V-venture lands a listen:

- **A-josh-f1:** per-letter Surface A scores on
  `spikes/samples-josh-f1/{a..z}.wav`. The `josh_stats_full.txt`
  artefact already has the objective half (peaks, f0); subjective
  half goes in the log.
- **B-acedio (frozen, for delta reference):** the v1 Surface B baseline
  on `spikes/samples/{a..z}.wav`. Already partially scored in the v1
  log; finish before V1's listen so the delta is attributable.

Cost baseline carries over from v1.

## Ventures

### V1 — Single-voice josh-f1 end-to-end

**Where:** No code change. `02_synthesis.py --samples-dir
spikes/samples-josh-f1/` on the fixture.

**Hypothesis:** Replacing the bank substrate is sufficient to move
Surface B static from "distractingly hash-y" to "no audible static"
without touching pipeline code. Predicted from the Surface A listen on
samples-josh-f1 (already done out-of-band — the "beyond the best" judgement).

**Surfaces:** A (already scored — confirm in log), B (primary).

**Measured + predicted:**

| Metric                       | Pre (acedio)  | Predicted post (josh-f1) |
|------------------------------|---------------|--------------------------|
| Output peak                  | ~0.95         | ~0.95 (sanity)           |
| static rating (B, ASR)       | TBD (v1 baseline) | +2–3 points          |
| character rating (B, ASR)    | TBD           | unchanged or +1          |
| cadence rating (B, ASR)      | TBD           | unchanged                |
| naturalness rating (B, ASR)  | TBD           | +1–2 points              |
| RTF                          | TBD           | unchanged (same code)    |
| Determinism                  | yes           | yes                      |

**Qual predictions:**

- Static drop is the headline. If V1's static rating gain is < +2, the
  Surface A judgement didn't transfer through synthesis, and either
  pitch shift or crossfade has been hiding a bigger problem than v1
  noticed.
- Character (f, s, t, x identifiability) should be at least as good.
  Josh's bank has the same letter set with cleaner recording — no
  reason character drops.
- If naturalness gains < +1, suspect the +6 pitch offset is over-
  shifting josh-f1's already-high f0 (~396 Hz). Spot-check at +0.

**Production cost:** Zero code. Disk cost: ~1.1 MB for the bank dir.

**Risk:** ~none. Reversible by changing `--samples-dir`.

**Stop condition:** If V1's Surface B static rating gain is ≥ +2 and
naturalness ≥ +1, V2/V3/V4 proceed. If V1 returns < +1 on static, stop
and re-examine — the pivot was wrong.

### V2 — Multi-voice mapping (pitch-ordinal + override)

**Where:** New mapping layer between diarization output and
`render_word`. Roughly: `cluster_speakers_by_pitch` already orders
speakers by mean f0; map ordinal k → voice in a curated pool
(`["josh-m4", "josh-m2", "josh-m3", "josh-f1"]` as a candidate pool;
m4 lowest = commentators, f1 highest = whoever is highest-pitched in
clip). Per-speaker override via CLI flag or sidecar JSON.

**Hypothesis:** Two distinct commentators rendered in two distinct
josh voices is audibly preferable to both in the same voice. Mapping
by pitch ordinal preserves "the bass-voice commentator sounds bass"
naturalness; minimises formant warp by keeping native and target f0
close (a secondary motivation — high-f0 source rendered at low pitch
shift means less spectral squash).

**Surfaces:** C (primary), B (single-voice still rendered for delta).

**Measured + predicted:**

| Metric                       | Pre (V1, single josh-f1)  | Predicted post (V2) |
|------------------------------|---------------------------|---------------------|
| Mapping consistency          | n/a (one voice)           | 1.0 (no oscillation)|
| Voice-switch density         | 0                         | matches turn density|
| static rating (C)            | V1 score                  | unchanged           |
| cadence rating (C)           | V1 score                  | unchanged           |
| speaker id rating (C)        | low (one voice)           | +2–3 points         |
| variety rating (C)           | low                       | +2 points           |
| RTF                          | V1 baseline               | +5–10% (multi-bank load) |
| Memory                       | 1 bank in RAM             | N banks in RAM      |

**Qual predictions:**

- Speaker id rating only earns its keep if a blind listener can tell
  the commentators apart by voice timbre alone (no transcript). If
  not, the mapping is decorative, not functional.
- Pitch ordinal is expected to be stable across a clip — `cluster_
  speakers_by_pitch` ranks by median f0, and commentator pitch
  identities don't swap mid-clip in F1 broadcasts. Predicted mapping
  consistency = 1.0; if it oscillates, the cluster ordering is
  itself unstable and the mapping layer isn't the bug.
- RTF impact small. Loading 4 banks is < 5 MB and load is one-time.

**Production cost:** ~80 LOC for mapping layer + CLI flag + override
parsing. New deps: none. Tests: per-mapping integration on one fixture.

**Risk:** If `cluster_speakers_by_pitch` mis-orders speakers (e.g. on
short clips where pyin estimates are noisy), the mapping flips between
runs. Mitigation: log the cluster ordering alongside each render so the
log records the assignment that produced the audible result.

**Stop condition:** If speaker id rating gain is < +1, the multi-voice
work isn't earning its keep — keep V1 only.

### V3 — Per-letter pitch jitter port

**Where:** `02_synthesis.py:render_word` (~line 709 area —
post-`pitch_shift_from_to`, pre-placement). Per-letter random uniform
jitter in semitones, drawn fresh per letter, unseeded.

**Hypothesis:** Josh's jitter (a `uniform(-J, +J)` semitones per letter,
J ≈ 0.5 in his default voice profile) is what makes his synthesis sound
"alive" vs the metronome quality of fixed-pitch acedio output. The
audible effect on Surface B is more important than the algorithmic
change.

**Surfaces:** B (primary).

**Measured + predicted:**

| Metric                       | Pre (V1)      | Predicted post (V3) |
|------------------------------|---------------|---------------------|
| Determinism                  | yes           | **no** (unseeded)    |
| naturalness rating (B)       | V1 score      | +0.5–1 point        |
| cadence rating (B)           | V1 score      | unchanged           |
| static rating (B)            | V1 score      | unchanged           |
| RTF                          | V1 baseline   | < +1% (1 RNG draw per letter) |

**Qual predictions:**

- Naturalness improves. Static doesn't (jitter doesn't touch the bank
  floor). Cadence doesn't (jitter is intra-letter pitch, not timing).
- Predicted J range: 0.3–0.8 semitones. Below 0.3, inaudible. Above
  0.8, the synthesised speech starts sounding "tipsy."
- Determinism loss is real and intentional. If we want repro for
  testing, a seedable mode behind a flag, but default unseeded so the
  output sounds live.

**Production cost:** ~5 LOC. New deps: none. New CLI flag:
`--pitch-jitter SEMITONES` (default 0.5).

**Risk:** Determinism loss breaks any golden-output test we might
write later. Pre-empt: golden test (when it lands in Phase 1) must
accept tolerance, not bit-exact — already specified in
`yipyap/CLAUDE.md` ("audio is not byte-stable across runs").

**Stop condition:** If naturalness rating gain is < +0.3, port wasn't
worth the determinism cost — keep but default to J=0.

### V4 — Yelling-on-RMS (optional)

**Where:** Synthesis-front-matter, per-word. RMS of the corresponding
voice-stem window above a threshold → route that word's render through
a "yelling" path (pitch +1.5 st, jitter +1.0 st, volume +0.10), per
josh's audio-manager.cjs composite.

**Hypothesis:** F1 commentary has emotional dynamics (overtake calls,
crashes) that flatten in V1/V2's uniform-pitch render. RMS gating
recovers them with no transcript dependency — pure signal.

**Surfaces:** B (single-voice fixture), C (multi-voice fixture for
realism).

**Measured + predicted:**

| Metric                       | Pre (V3)    | Predicted post (V4) |
|------------------------------|-------------|---------------------|
| naturalness rating           | V3 score    | +0.5 if a yelling event lands in fixture, ±0 otherwise |
| static rating                | V3 score    | unchanged           |
| Mapping consistency          | V3 score    | unchanged (yelling is overlay, not voice swap) |
| RTF                          | V3 baseline | < +2% (one RMS pass) |

**Qual predictions:**

- Effect is event-driven; verdict depends entirely on whether the
  60–90s Abu Dhabi window contains a high-RMS moment. If it doesn't,
  pick a clip that does for V4's listen (or accept that V4 is
  unverified on this fixture).
- Yelling composite is plausibly *too much* on F1 (commentator yells
  are not anime-girl yells). Predict the volume +0.10 lift in
  particular might over-pop; consider attenuating to +0.05.

**Production cost:** ~30 LOC for the RMS gate + yelling renderer
branch. New CLI: `--yelling-threshold DBFS` (default −12 dBFS).

**Risk:** RMS gating fires on background noise (engine sound, crowd)
not just yells. Mitigation: gate on voice-stem RMS specifically
(already separated), not mixed RMS. If still noisy, defer or refine.

**Stop condition:** If naturalness gain is < +0.3 on a clip *with* a
yelling event, route is wrong somehow — drop it.

### V5 — Cross-bank A/B at Surface C

**Where:** New tooling, not a code change to `02_synthesis.py`. Render
the same fixture through V1+V2+V3(+V4) using two different voice pools
(e.g. josh-male-only vs josh-mixed) and concatenate the outputs into a
single A/B comparison file in `samples-compare/`.

**Hypothesis:** Voice pool composition has audible effect on "what the
broadcast feels like" independent of mapping logic. A male-only pool
sounds like men talking; a mixed pool sounds like a mixed booth.
Whether one is preferable is a stylistic question; this is the listen
that lets us decide.

**Surfaces:** C (primary; comparison).

**Measured + predicted:**

| Metric                       | A: male-only  | B: mixed       |
|------------------------------|---------------|----------------|
| speaker id rating            | TBD           | TBD            |
| variety rating               | TBD           | TBD            |
| naturalness rating           | TBD           | TBD            |

No predictions — this is the stylistic decision point, by design open.

**Production cost:** ~20 LOC of comparison tooling (or shell script).
Reuses V1–V3.

**Risk:** None. Pure listen.

**Stop condition:** Pick the preferred pool, write the decision into
findings, move on. Either outcome is fine; the venture's purpose is
to make the choice deliberately.

## Sequencing and gates

```text
V0 baselines (cost + Surface A on josh-f1 + Surface B on acedio)
   |
   V1  ── stop if static gain < +1 (pivot was wrong)
   |
   V2  ── stop if speaker id gain < +1 (multi-voice not earning keep)
   |
   V3  ── stop if naturalness gain < +0.3 (jitter not worth it)
   |
   V4  ── optional; gate on clip having a yelling event
   |
   V5  ── stylistic A/B; pick pool, document
```

Each venture is one commit (or one PR if it touches `02_synthesis.py`
shape). Surface A measurements per bank go into the log with the
venture entry. Surface B/C listens go into the log; if a venture
graduates a generalizable lesson, it joins `docs/lessons.md` after
Phase 1 lands.

## Stopping criteria for the whole spike

The plan is finished when **either**:

1. V3 has landed, V4/V5 listened to, and there is a recorded
   recommendation in `docs/lessons.md` for what defaults Phase 1
   should ship (which bank, which jitter default, whether yelling
   ships, which pool), **or**
2. V1 returns < +1 static gain — pivot was wrong, regroup. Likely next
   move would be re-examining pitch_shift / crossfade as the hidden
   bottleneck v1 hypothesised in E4/E5.

## Carry-over from v1

These v1 items are not v2 ventures but are still operational facts:

- The E1a code change in `00_extract_bank.py` (DC remove before
  peak-norm) stays. It's a correctness fix, validated by the log; not
  worth reverting just because its predicted perceptual win didn't
  materialise.
- The `02-synthesis-log.md` baseline section (HF/RMS/DC table on the
  acedio bank) is still useful as a reference floor — don't delete.
- The Surface A/B convention from v1 stays and extends to C.

## Risks (plan-level)

- **Bank disk creep.** 8 voices × ~1.1 MB = ~9 MB checked-in audio.
  Compare to the `.gitignore` rule: spike inputs/outputs no, fixtures
  yes. These extracted banks live in the "fixture-like" category but
  they came from josh, not from us — flag for user before V2 commits
  add them, since the user asked us not to commit audio we didn't
  intend to commit.
- **Reproducibility of josh extraction.** `extract_josh.py` depends on
  having `/tmp/josh/` already populated from the installed package.
  Document the prerequisite in the script header (or copy the Ogg
  sources into a checked-in fixture dir) so a future run isn't
  load-bearing on whatever was in /tmp on 2026-05-16.
- **Diarization quality on F1 audio.** `cluster_speakers_by_pitch` was
  built against general voice clips; F1 commentary has team-radio
  cut-ins, crowd noise, and overlapping commentators. If V2 mapping
  oscillates, the bug is upstream of v2's mapping layer — fix the
  diarization, not the mapping.
- **josh-f3 and others remain unspiked.** If V1 returns acceptable
  but not great, V1.5 (try josh-f3 / josh-m2 single-voice before
  committing to multi-voice) is worth a beat. Implicit in the
  baseline V0 if Surface A scores are recorded per voice.

## Why this plan exists, in one paragraph

v1 was right to ask whether the static was pipeline-amplified or
bank-intrinsic. The answer turned out to be *bank-intrinsic and
specifically a quantization floor*, which v1 didn't anticipate as the
dominant term. v2's job is to make the bank replacement land cleanly,
extract whatever multi-voice value the new substrate makes available,
and port the jitter idea that the reference implementation (josh)
demonstrated is the highest-value pipeline change of all. Everything
else in v1 is parked until V1 measures.
