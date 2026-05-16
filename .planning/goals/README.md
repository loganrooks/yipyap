# Goals archive

This directory holds `/goal` prompts used to drive autonomous Claude Code work
on this project. Each file is a single `/goal` invocation, with status
metadata in the header and the copy-pasteable prompt body as a fenced block.

## Naming

`NN-short-topic.md` where `NN` is a zero-padded sequence number. Sequence
reflects the order goals were drafted (not necessarily executed). Numbers are
permanent — if a goal is abandoned, mark it `status: abandoned` rather than
renumbering.

## Status values

- `done` — goal was fired and the condition was met. The prompt body is
  archived verbatim for traceability. Do not re-fire.
- `queued` — drafted but not yet fired. Ready to copy-paste into `/goal`.
- `superseded` — was queued but replaced by a later goal. Keep the file for
  history; the header notes which goal replaced it.
- `abandoned` — drafted but no longer planned. Keep for history.

## How to use

When a goal in this directory is `queued`, copy the contents of the fenced
`/goal …` block (including the leading `/goal`) into the Claude Code prompt
and submit. Auto mode should be on for unattended runs. Once the condition
clears, update the file's status to `done` and add a brief outcome note in the
header.

## File structure (progressive disclosure)

`/goal` conditions are capped at **4000 characters**. To accommodate richer
context without exceeding that ceiling, goal files have two layers:

1. **Body prose** above the fenced block (`## Intent (full detail)`,
   `rationale:` frontmatter) — for human readers and for the agent to read
   if it wants the longer story. Not bounded.
2. **The fenced `/goal …` block** — the compact, copy-pasteable directive
   that gets pasted into the prompt and is what the small fast evaluator
   model judges turn-by-turn. Bounded to ≤4000 chars.

When writing a new goal: draft the verbose intent first, distill the fenced
block from it. Measure the fenced block with
`awk '/^```$/{f=!f; next} f{print}' file.md | wc -c` and trim until under
4000. The evaluator can only see what's surfaced in the chat transcript, so
the fenced block must be self-sufficient — the body prose is for humans, not
for the evaluator.

## Why a directory

`/goal` is session-scoped — it only persists for the lifetime of the chat. If
the session ends mid-loop, or you want a second-opinion review of the goal
text, or you want to chain goals deliberately, having the prompts on disk is
the only durable record.

This directory is committed. Goals can reveal intent and constraints that
PR-history alone wouldn't.
