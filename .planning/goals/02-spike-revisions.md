---
status: done
created: 2026-05-15
fired: 2026-05-15
phase: Phase 0
summary: Revise docs/spike-plan.md to split Spike B into cadence/timbre/combined sub-tests, require multi-clip Spike A, and add a concrete listening protocol. Propagate matching changes into spikes/02_synthesis.py (--samples-dir, --pitch-offset, new output naming), README.md, findings.md, and .gitignore.
depends-on: 01-spike-setup.md
outcome: |
  Met. docs/spike-plan.md updated (Spike A multi-clip 20-40s × 2-3 stressors;
  Spike B split into cadence/timbre/combined sub-tests; Listening protocol +
  Known knobs subsections added before Working directory). 02_synthesis.py
  rewritten with --samples-dir and --pitch-offset, output naming follows bank
  kind (spike-b-cadence.wav / spike-b-real.wav + -mixed.wav variants),
  spike-b-onset-direct.wav retired. README.md updated with 3-mode invocations
  and listening protocol mirror. findings.md template gained multi-clip A
  matrix + Cadence/Timbre/Combined B sections + pitch offset field.
  .gitignore now ignores spikes/samples/. All four smoke modes exit 0 and the
  missing-dir error path exits 2 with a clear stderr message. Staged only
  (no commit).
rationale: |
  Spike B as currently specified couples two failure modes that should be
  separable: sample timbre and onset cadence. If the output sounds bad with
  synthesized sine samples, you can't tell which side failed.

  Spike A on one clip answers "does Demucs work on THIS clip" — not "does
  Demucs work for the project." Real sports audio varies (crowd peaks, music
  swells, overlapping commentators); one clip is a single sample.

  "Listen and write a verdict" is too loose; identical clips can yield
  different verdicts depending on mood.
---

## Intent (full detail)

Three independent improvements to Phase 0, applied in lockstep across plan and
scaffold.

### B-axis: split Spike B into separable questions

The current synthesis spike asks one question — "does this sound like animalese
over commentary cadence?" — that conflates two failure modes:

- **Cadence:** do events fire when the commentator is speaking, with the right
  rhythm? (Mostly a function of VAD, onset detection, and pitch estimation
  quality.)
- **Timbre:** do the samples themselves sound like animalese? (Purely a
  function of the sample bank.)

The current scaffold uses synthesized 3-harmonic sines as the placeholder
bank. Those won't sound like animalese no matter how good the cadence is. If
we listen to the output and dislike it, we won't know which side failed.

The fix: render three distinct outputs.

- `spike-b-cadence.wav` — the ugly inline sine bank, listened to *only* for
  rhythm. Question: does it sound like the original speaker, in cadence?
- `spike-b-real.wav` — a real animalese sample bank (user-supplied from
  `spikes/samples/`). Question: do the samples sound like animalese?
- `spike-b-mixed.wav` — real bank + background stem from Spike A. Question:
  does the combined output deliver the intended listening experience?

Failure modes become diagnosable.

### Spike A on multiple clips

The plan says "pick one real source clip (~30s ... )." One clip answers "does
the chosen separation model work on this clip." Sports audio varies: crowd
peaks during a play; music swells over commentary; overlapping commentators
(rare but real). To get a verdict that generalises, run 2–3 clips covering
distinct stressors. The model verdict is then an aggregate across clips, not
a single sample.

### Concrete listening protocol

"Listen and write a verdict" varies with mood. Tighten:

- Spike A: A/B the same 10s segment from the two models back-to-back, eyes
  closed (avoid model-name bias).
- Spike B: listen at 0.75× speed once to catch alignment slips that mask at
  full speed.

### Scaffold knobs the script needs

To support the cadence/timbre split, `02_synthesis.py` needs a way to swap
banks without code edits and a way to compensate for the high-tessitura
character of animalese (it's pitched up — following commentator pitch 1:1
will pull samples into muddy bass).

- `--samples-dir <PATH>` — load bank from a directory of .wav files. Default
  remains the inline sine bank.
- `--pitch-offset <SEMITONES>` — shift target pitch up/down before
  pitch-shifting the sample. Default 0; suggested first try is 12 (one octave
  up) once a real sample bank is in place.

Output naming reflects which bank was used, so the cadence-only test and
timbre test don't clobber each other.

### Notes baked into the plan

Two non-failure modes worth documenting so the listener doesn't
misinterpret:

- VAD on continuous commentary returns ~one big voiced region. Expected.
  Phrase/breath-level gating is Phase 2 work, not a Spike B failure.
- Animalese is high-tessitura. Default pitch mapping may sound muddy; that's
  a knob, not a refutation of the approach.

## /goal prompt (≤4000 chars)

```
/goal Revise Phase 0 plan and propagate revisions into the spike scaffold.

A. docs/spike-plan.md — update method sections + add new subsections.
   - Spike A: explicitly call for 2–3 clips covering different stressors (e.g. clean talk over light crowd; music swells; crowd peaks). Spike A outputs are per (clip × model). Model verdict aggregates across clips.
   - Spike B: split into three deliverable WAVs from separable questions:
     (i) spike-b-cadence.wav — inline sine bank (cadence-only test).
     (ii) spike-b-real.wav — user-supplied real animalese bank from spikes/samples/ (timbre test).
     (iii) spike-b-mixed.wav — real bank + background stem (combined artistic verdict).
   - Add "Listening protocol" subsection: A/B the same 10s segment from both Spike A models back-to-back, eyes closed; for Spike B, listen once at 0.75× to catch alignment slips.
   - Add "Known knobs / non-failures" subsection: (i) VAD likely returns one big voiced region on continuous commentary — expected; finer phrase/breath gating is Phase 2. (ii) animalese is high-tessitura; try --pitch-offset 12 if default mapping sounds muddy.

B. spikes/02_synthesis.py — extend for cadence/timbre split:
   - --samples-dir <PATH>: load bank from a dir of .wav files (one per file); omitted → inline sine bank.
   - --pitch-offset <SEMITONES> (int, default 0): shift target pitch N semitones before sample pitch-shifting.
   - Output naming reflects bank: inline → spike-b-cadence.wav (+ spike-b-cadence-mixed.wav with background); --samples-dir → spike-b-real.wav (+ spike-b-real-mixed.wav with background). Retire spike-b-onset-direct.wav.
   - If --samples-dir is missing/empty/has no .wav files, raise a clear error and exit non-zero. No silent fallback.

C. spikes/README.md — show all three Spike B runs (cadence, real, mixed) + --pitch-offset note. Mirror the plan's Listening protocol section.

D. spikes/findings.md — update template:
   - Multi-clip Spike A verdict table (clip × model: voice / background / runtime / artifacts / verdict).
   - Spike B verdicts split into Cadence / Timbre / Combined sections.
   - "Pitch offset chosen for Phase 1: TODO" field.

E. .gitignore — add `spikes/samples/` so user-supplied bank audio is not tracked.

SMOKE:
   (i) Generate a stub bank at /tmp/yipyap_test_bank/ with ~4 short .wav files.
   (ii) Run 02_synthesis.py on the existing yipyap_smoke voice stem in four modes: defaults (→ spike-b-cadence.wav); --samples-dir /tmp/yipyap_test_bank/ (→ spike-b-real.wav); --samples-dir with background (→ spike-b-real-mixed.wav); --pitch-offset 12 (any mode). All exit 0; surface exit codes and file lists.
   (iii) Missing-dir error path exits non-zero with a clear stderr message.

CONSTRAINTS:
- Do NOT modify pyproject.toml, VISION.md, ROADMAP.md, docs/architecture.md, or docs/pr-plan.md.
- Do NOT change exit criteria, working-directory section, or "what NOT to do" inside docs/spike-plan.md.
- Do NOT modify spikes/01_separation.py beyond doc comments.
- Do NOT write tests or create src/yipyap/.
- Do NOT git commit. Staging only.
- Do NOT write listening verdicts — TODO placeholders only.
- Do NOT commit real animalese samples or any audio.

EVIDENCE:
- `git diff -- docs/spike-plan.md spikes/02_synthesis.py spikes/README.md spikes/findings.md .gitignore`
- All four smoke runs + the missing-dir error case (exit codes + produced files).
- `git status --short`; `git check-ignore -v spikes/samples/x.wav`.

BOUND: stop after 20 turns. If a smoke run fails on the same root cause >2 attempts, STOP and report.
```
