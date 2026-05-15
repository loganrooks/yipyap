# Working on yipyap

This file is for any coding agent (Claude or otherwise) picking up work in this repo.
Humans, read it too — it's also the team agreement.

## What this project is

A CLI that swaps sports commentary for Animal Crossing "animalese" while keeping the
background audio. See `VISION.md` for the full statement. If your change makes one of
the success criteria there unreachable, stop and raise it.

## Documents you must read before working

1. `VISION.md` — goal, success criteria, non-goals.
2. `ROADMAP.md` — phases. Know which phase you're in.
3. `docs/architecture.md` — pipeline shape and module contracts. **Do not change
   contracts in passing.** If a contract has to change, that's its own PR.
4. The relevant plan: `docs/spike-plan.md` (Phase 0) or `docs/pr-plan.md` (Phase 1).

## Workflow

- Branch from `main`. Branch name follows the plan (`phase-1/pr-NN-topic`,
  `spike/<name>`, `phase-2/<topic>`).
- One PR = one item from the plan. Don't bundle.
- Every PR description includes: scope, acceptance criteria, what was tested, what was
  not tested. Acceptance criteria come from the plan, not invented on the spot.
- `main` always works once Phase 1 is in. If your PR breaks the CLI, it isn't ready.
- Listening tests matter. Some regressions are only audible. When you change anything
  that affects output, you (or a human) must listen, and the listen goes into
  `docs/listening-log.md`.

## Commands

After PR 1 lands:

```
make install     # pip install -e . with dev deps
make test        # pytest
make lint        # ruff / formatting check
make run IN=path/to/in.mp3 OUT=path/to/out.mp3
```

These are placeholders until PR 1 exists; PR 1 makes them real.

## House rules

- **Python 3.11+.** Type hints everywhere. `from __future__ import annotations` at the
  top of each module.
- **Dataclasses** for the contract types (`SeparationResult`, `VoiceEvent`). No dicts
  across stage boundaries.
- **Numpy arrays as `float32` mono or stereo.** Document shape in every function that
  takes or returns audio.
- **No global state.** Each stage function is pure given its inputs (and the on-disk
  files it references).
- **No silent fallbacks.** If something fails, raise `YipyapError` with a useful message.
  Do not invent zero-filled audio "just to keep going."
- **Small PRs.** If a PR exceeds the scope in the plan, split it.
- **Don't commit audio you didn't intend to commit.** Fixtures yes; spike inputs and
  outputs no. The `.gitignore` is calibrated for this — don't override it casually.

## Specific things not to do

- Don't add a web UI. Don't add a GUI. Don't add a "library mode" before Phase 3.
- Don't introduce real-time / streaming code paths. Offline batch only.
- Don't refactor module contracts mid-PR.
- Don't regenerate golden test outputs without listening to them and recording the listen.
- Don't add multi-speaker diarization. Voice stem is treated as one voice.
- Don't transcribe unless the spike found that transcription is needed (see
  `docs/architecture.md` "Decisions deferred").

## When to ask vs. when to decide

Decide on your own:
- Internal implementation choices that don't change module contracts.
- Test details, fixture data shape, CI configuration.
- Library choices within a module (e.g. which onset detector inside `analyzer/onsets.py`).

Stop and ask:
- Anything that would change a function signature in `docs/architecture.md`.
- Anything that conflicts with `VISION.md`.
- Anything that would add a top-level dependency not already implied by the plan.
- Acceptance criteria that look ambiguous.

## Tests

Unit tests per module (`tests/test_<module>.py`). One integration test
(`tests/test_pipeline.py`). One golden test (`tests/test_golden.py`, perceptual).

The golden test uses a tolerance because audio is not byte-stable across runs of
neural models. Don't replace this with strict equality.

## When you finish a PR

- All listed acceptance criteria met, literally.
- `make test` green. CI green if it exists.
- PR description filled out per the workflow rules above.
- If the change affects output audio, listening-log entry added.
- Self-review: re-read the diff before requesting review.

## When in doubt

Re-read `VISION.md`. The point of this project is a specific listening experience.
Anything that doesn't serve that is out of scope.
