# yipyap

A CLI that takes a sports clip and replaces the commentary with Animal Crossing-style
animalese, preserving the background (crowd, music, transitions).

```
yipyap input.mp3 output.mp3
```

Status: **planning**. No code yet. See the docs below.

## Read me in this order

1. [`VISION.md`](VISION.md) — what we're building and why, success criteria, non-goals.
2. [`ROADMAP.md`](ROADMAP.md) — phases (spikes → MVP → quality → polish) and exit
   criteria for each.
3. [`docs/architecture.md`](docs/architecture.md) — pipeline diagram and module
   contracts.
4. [`docs/spike-plan.md`](docs/spike-plan.md) — the two Phase 0 experiments that must
   run before we scaffold real code.
5. [`docs/pr-plan.md`](docs/pr-plan.md) — Phase 1 PR-by-PR breakdown.
6. [`CLAUDE.md`](CLAUDE.md) — conventions for anyone (human or agent) working in the
   repo.

## Why so much planning for a small project

The two unknowns — whether source separation works well enough on sports audio, and
whether onset-aligned animalese sounds right — are qualitative. They can only be
resolved by listening. The phasing exists to put those listening tests first, then
build a clean pipeline around what survives.

## License

Private project. Not licensed for redistribution.
