# yipyap — Vision

## What this is

A command-line tool that takes a sports clip (commentary plus crowd, music, transitions,
game audio) and produces the same clip with the commentary replaced by Animal Crossing
"animalese" gibberish that follows the original speech cadence and pitch contour.
Background audio is preserved.

In one sentence: *swap the play-by-play for Tom Nook, keep everything else.*

## Why

For fun. It's a small, self-contained audio project where the artistic outcome can only be
known by listening. That makes it a good vehicle for disciplined experimentation: spike
the unknowns first, then build a clean pipeline around what survives.

## Success criteria

The MVP is successful when:

1. A one-line invocation — `yipyap input.mp3 output.mp3` — produces an output file with
   commentary replaced by animalese.
2. On a representative 30-second sports clip, the background (crowd, music, game sounds)
   is preserved with no obvious artifacts from the source-separation step.
3. The animalese track rhythmically aligns with the original commentary — i.e., listening
   blind, you can tell which speaker is "talking" at any moment.
4. Loudness of the animalese is roughly matched to the original commentary so neither
   buries the background nor gets buried by it.
5. The pipeline runs end-to-end on CPU in reasonable time (target: ≤ real-time × 5 on a
   laptop, looser if needed).

A *stretch* success is that the output is genuinely funny to listen to.

## Non-goals

- Live / real-time processing. Offline batch only.
- Video. Audio in, audio out.
- Lip-sync. There's no video, so there's nothing to sync to.
- Faithful transcription of what the commentator actually said. Animalese is gibberish
  on purpose.
- A web UI, hosted service, or anything beyond a local CLI.
- Multi-speaker diarization. If two commentators overlap, we treat the mix as one voice
  stem.
- Cross-platform polish. Mac/Linux first; Windows is best-effort.

## Constraints / principles

- **Spike before scaffold.** Two unknowns (separation quality on sports audio, and
  whether onset-aligned animalese sounds right) determine the architecture. Resolve them
  in throwaway scripts before committing to module shapes.
- **Onset/pitch path first.** Default plan is to skip transcription and drive animalese
  from VAD + onset detection + pitch tracking on the isolated voice stem. Fall back to a
  transcription/forced-alignment path only if the spike proves onset detection too noisy.
- **Modules behind contracts.** Each pipeline stage is a module with a documented
  function signature. Stages do not know about each other's internals. See
  `docs/architecture.md`.
- **Main stays runnable.** Once Phase 1 is in, every PR keeps `yipyap input.mp3
  output.mp3` working end-to-end.
- **Listening is part of the test loop.** Some regressions can only be detected by ear.
  We will commit small fixture audio + golden outputs and require manual review when they
  change.

## What this document is for

This file pins the goal so we don't drift. If a future change makes one of the success
criteria unreachable or contradicts a non-goal, that's a signal to either revise this
document deliberately or stop the change.

See also:
- `ROADMAP.md` — phases and exit criteria
- `docs/architecture.md` — pipeline and module contracts
- `docs/pr-plan.md` — Phase 1 PR sequence
- `docs/spike-plan.md` — Phase 0 spike checklist
- `CLAUDE.md` — conventions for coding agents working in this repo
