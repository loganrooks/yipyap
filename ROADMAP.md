# yipyap — Roadmap

Five phases. Each has a goal, exit criteria, and a guard. The guard is the thing that
should stop us moving on if we haven't actually achieved the phase.

---

## Phase 0 — Spikes (throwaway)

**Goal:** Resolve the two artistic/quality unknowns before committing to architecture.

- **Spike A — Source separation.** Run a current open-source separation model (Demucs
  htdemucs_ft, and one alternative) on a real sports clip. Listen to the voice stem and
  the no-voice stem. Decide whether quality is acceptable.
- **Spike B — Onset-aligned animalese.** Given the voice stem from Spike A, detect
  syllable onsets + pitch, fire one animalese sample per onset at the detected pitch.
  Listen. Decide whether the result feels like "animalese over commentary cadence" or
  like noise.

**Exit criteria:**
- A written `spikes/findings.md` (not committed yet — lives in the throwaway folder) with
  the verdict on each spike and a recommended path.
- A decision recorded for: which separation model, which onset/pitch tools, transcription
  fallback yes/no.

**Guard:** If Spike B sounds bad, do *not* proceed to Phase 1 with the onset-based plan.
Either iterate the spike with the transcription-based fallback, or revise VISION.

**Branch convention:** `spike/<name>` — never merged to main. Findings are summarized
into `docs/architecture.md` before any Phase 1 code lands.

---

## Phase 1 — MVP CLI

**Goal:** End-to-end working command. One input, one output, defaults only. Quality is
"acceptable," not "polished."

**Exit criteria:**
- `yipyap path/to/in.mp3 path/to/out.mp3` runs cleanly on a 30-second clip and produces
  a playable output with animalese where commentary used to be.
- All five modules (separator, analyzer, synthesizer, mixer, cli) have unit tests on
  fixtures.
- One integration test using a short fixture clip passes in CI.

**Guard:** Do not begin Phase 2 until a real sports clip has been processed and listened
to and the listener has signed off in writing (a line in `docs/listening-log.md`).

**Branch convention:** `phase-1/pr-NN-<topic>`. PR-by-PR plan in `docs/pr-plan.md`.

---

## Phase 2 — Quality pass

**Goal:** Make the output sound good enough to enjoy.

Work items (rough; firmed up at start of phase):
- Loudness matching between animalese and original voice (LUFS-based).
- Voiced/unvoiced gating — no animalese fires during breaths, silences, pauses.
- Pitch contour smoothing — currently per-onset pitch may jitter; smooth over voiced
  regions.
- Better onset detection — tune to commentary speech, not to music.
- Sample-bank pitch shifting that doesn't introduce chipmunk/timestretch artifacts.

**Exit criteria:**
- A side-by-side listening test of three clips shows Phase 2 output preferred over
  Phase 1 in all three.
- New listening-log entries with notes.

**Guard:** No new features in this phase. If something feels like Phase 3, it goes in
the backlog.

**Branch convention:** `phase-2/<topic>`.

---

## Phase 3 — Polish & configurability

**Goal:** CLI feels like a real tool, not a script.

- Flags: `--voice <preset>`, `--pitch-mode follow|random|fixed`, `--intensity 0..1`,
  `--keep-temp`, `--verbose`.
- Sample preset library (different villager-style voices).
- Progress reporting.
- Helpful error messages on bad input.
- Optional config file `~/.yipyap.toml`.

**Exit criteria:**
- `yipyap --help` documents every flag.
- A README "recipes" section showing typical invocations.

**Branch convention:** `phase-3/<topic>`.

---

## Phase 4 — Optional extensions

Anything past Phase 3 is optional and decided then, not now. Candidates: batch mode,
GPU acceleration, long-file streaming, a tiny local web UI for drag-and-drop. Add to
this section as ideas land; do not commit to them.

---

## How phases relate to branches and PRs

- `main` always works once Phase 1 is in.
- Phases progress sequentially. We do not start Phase N+1 PRs until Phase N's exit
  criteria are met.
- Spikes are an exception: they live on `spike/*` branches and are not merged.
- Each PR lists which phase and which exit criterion it advances.
