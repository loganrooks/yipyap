# Speaker workflow plan

> **Status:** Draft, 2026-05-16. Not yet adopted into `VISION.md` or
> `ROADMAP.md` — this document exists so we can read the proposed shape
> cold before committing to it. Where it contradicts `VISION.md`, the
> contradictions are listed explicitly at the bottom; resolve those
> first, then this becomes load-bearing.

## Why this document exists

yipyap as currently scoped is a stateless `input.mp3 → output.mp3` CLI.
That shape stops working as soon as we want:

1. Multiple voices in the output (V2 of `spikes/02-synthesis-plan-v2.md` —
   that document lands separately via PR #9 / `phase-0/bank-pivot`; if
   you're reading this on `main` before that PR merges, the v2 plan
   isn't in-tree yet).
2. A speaker's identity to persist across clips so the same commentator
   gets the same voice in every broadcast we process.
3. The user to label discovered speakers so subtitle text-boxes (if
   that work lands) and voice assignments use real names.

Each of those adds state and asks the user to participate in the
processing instead of running one command and walking away. That's a
real shift; this doc is where we work out whether the shift is coherent
before we start moving code.

## The unsupervised constraint

There are no ground-truth labels. Diarization produces anonymous
clusters; embedding similarity matches one cluster to another. **The
system never knows who's talking** — it discovers groupings and a
human supplies meaning. Every workflow decision below flows from that.

Implications:

- "Accuracy" as classically scored does not apply. The metrics that do:
  - *Cluster purity within a clip* — did diarization split one speaker
    into two clusters, or merge two into one? Both are correctable.
  - *Cross-clip stability* — does Crofty's profile keep matching the
    same anonymous cluster across new clips after we labeled him?
  - *Time-to-label per new clip* — the real UX metric. The auto-match
    is only useful if it makes this small.
- The library is a curated artifact, not a static model. It grows and
  occasionally needs hygiene. Library hygiene is a first-class
  workflow concern, not a paper-cut.
- The labeling step cannot be skipped. It can be made fast (one-button
  confirmations on high-confidence matches), but never zero. Design
  for it as a feature, not a friction point.

## Pipeline shape: ingest / label / render

Three stages, each with cached artifacts on disk. The split exists so
that re-running the cheap repeatable stage (render) doesn't re-trigger
the slow stages (ingest), and so the human-in-loop stage (label) is
separable from both.

```text
clip.mp4
   │
   ▼ ingest         heavy: separation + ASR + diarization + embeddings.
   │                run once unless source clip changes.
   │
clip.ingest.json     ── anonymous clusters, embeddings, ASR, provenance
clip.speakers.json   ── pre-label sidecar: proposed matches per cluster
                        (written by ingest, edited by label)
   │
   ▼ label          interactive: human listens + names clusters.
   │                proposes matches against library; user accepts/edits.
   │                rewrites clip.speakers.json post-validation.
   │
clip.speakers.json   ── post-label: confirmed labels + ignore/merge/split state
~/.yipyap/speakers/  ── library state, updated on successful label
   │
   ▼ render         fast, deterministic: synthesizer + mixer + overlay.
   │                re-runnable after profile tweaks without re-ingest.
   │
clip.render.json    ── per-letter timing + voice-bank assignments
clip-out.mp4        ── final audio (and overlay, if video phase lands)
```

Caching rule: each artifact records the mtime + sha of its source
inputs **and** a tooling-version fingerprint (yipyap version, schema
version, and the named backends — ASR model, diarization model,
embedding model). A stage re-runs when any of those change. Schema
or backend changes invalidate stale caches even if the source file
is byte-identical — otherwise upgrading yipyap would silently render
new clips against old analysis. See the `clip.ingest.json` schema
below for the exact fields.

### Per-stage detail

#### Ingest

Inputs: `clip.mp4` (or .wav/.mp3).

Operations:
1. Separation (MDX-Net, per `docs/architecture.md` Spike A decision)
   → `voice.wav`, `background.wav`.
2. ASR on the original clip (faster-whisper or mlx-whisper, already in
   use in `02_synthesis.py --asr-input`) → word list with timings.
3. Diarization on `voice.wav` (`pyannote/speaker-diarization-3.1` or
   equivalent) → list of turns with anonymous cluster IDs.
4. Per-cluster embedding (ECAPA-TDNN or pyannote's built-in) → one
   fixed-length vector per cluster.
5. Per-cluster listening preview: concatenate 10–15s of representative
   audio per cluster → `clip-speakers/speaker_0_preview.wav` etc.
6. Match each cluster's embedding against `~/.yipyap/speakers/*.json`,
   record top-3 matches with cosine similarity.

Output: `clip.ingest.json` (see schema below), the pre-label
`clip.speakers.json` sidecar (proposed matches per cluster, ready
for the label stage to read), and the `clip-speakers/` listening-kit
directory.

Idempotent: re-running ingest on an unchanged clip is a no-op (cache
hit). Re-running after the library has gained speakers should refresh
proposed matches without re-doing separation/ASR — split the work so
match-refresh is its own subcommand (`yipyap ingest --refresh-matches`).

#### Label

Inputs: `clip.ingest.json`, library state, optionally `clip.speakers.json`
from a prior pass.

Operations: the only stage with a human in the loop. Default flow is
not interactive in the TUI sense — the user opens the sidecar in their
editor, reviews proposed matches, edits names, saves, re-runs. A more
opinionated TUI can come later; the JSON-edit flow is the durable
baseline because the artifact is the source of truth.

For each anonymous cluster, the sidecar shows:

- Preview path (`clip-speakers/speaker_0_preview.wav`)
- Total speaking time and utterance count
- Top-5 transcribed words (helps recognise a familiar phrase)
- Mean f0
- Proposed library matches with confidence tier (HIGH / MID / LOW)
- A `label` field for the user to fill in
- A `merge_with` field (optional) if diarization over-split
- A `split` field (optional) if diarization under-merged
- An `ignore` flag (optional) for noise, PA announcers, jingles

Confidence tiers gate ask volume:

- **HIGH (cos > 0.8 vs an existing profile)**: sidecar pre-fills `label`
  with the matched name. User reviews; default-accept makes most
  HIGH-only clips zero-friction once the library is established.
- **MID (0.5–0.8)**: sidecar shows "looks like X (0.72), confirm?"
  User accepts, rejects (auto-promotes to LOW), or renames.
- **LOW (< 0.5)**: sidecar shows "no good match — name?" User supplies
  a name (new profile created) or marks `ignore`.

On save:
1. Validation: every cluster must have one resolved disposition —
   `label` set, `ignore: true`, `merge_with: <other_cluster_id>`,
   or `split: {...}` (the four valid terminal states). Anything else
   is an error.
2. Library updates: new labels create profiles; existing profiles get a
   new contribution entry (see library schema). Centroid embeddings
   recompute from contributions. Ignored / merged / split clusters do
   not contribute to any profile.
3. `clip.speakers.json` is rewritten with confirmed dispositions only
   (the proposed-match noise is dropped — the durable artifact is the
   user's decision, not the candidates). All four disposition kinds
   are preserved in the post-label artifact so render can resolve
   each ASR word's original cluster_id deterministically (see the
   post-label schema below).

#### Render

Inputs: `clip.ingest.json` (for timings), `clip.speakers.json` (for
assignments), `~/.yipyap/speakers/*.json` (for voice-bank choices and
modulation knobs), voice banks under `~/.yipyap/banks/`.

Operations:
1. For each ASR word, look up its speaker_id (from the diarization
   turn it falls inside) and the speaker's profile.
2. Load that speaker's voice bank, apply their pitch_adjust + jitter +
   yelling threshold.
3. Synthesize animalese per-word using the existing `render_word`
   path, multi-bank-aware.
4. Mix with the background stem from ingest.
5. Emit `clip.render.json` with per-letter timing schedule for the
   overlay phase to consume.
6. Encode the output (audio-only for Phase 1/2; with overlay for the
   eventual video phase).

Fast and deterministic. Re-rendering after a profile tweak should not
trigger ingest re-runs.

## Sidecar schemas

These are draft schemas — pin them in `docs/architecture.md` once this
plan is adopted.

### `clip.ingest.json`

```json
{
  "yipyap_version": "0.0.0-dev",
  "schema_version": 1,
  "source": {
    "path": "clip.mp4",
    "sha256": "...",
    "mtime": "2026-05-16T21:30:00Z",
    "duration_s": 30.0,
    "ingested_at": "2026-05-16T21:45:00Z"
  },
  "tooling": {
    "asr_backend": "faster-whisper",
    "asr_model": "large-v3-turbo",
    "diarization_backend": "pyannote-3.1",
    "embedding_backend": "ecapa-tdnn"
  },
  "asr": {
    "words": [
      {"text": "Verstappen", "start_s": 1.20, "end_s": 1.85, "cluster_id": 0},
      {"text": "ahead", "start_s": 1.92, "end_s": 2.10, "cluster_id": 0}
    ]
  },
  "diarization": {
    "turns": [
      {"start_s": 1.18, "end_s": 8.40, "cluster_id": 0},
      {"start_s": 8.50, "end_s": 14.20, "cluster_id": 1}
    ]
  },
  "clusters": [
    {
      "cluster_id": 0,
      "n_utterances": 312,
      "speaking_seconds": 18.4,
      "mean_f0_hz": 142.0,
      "top_words": ["verstappen", "into", "turn", "and", "now"],
      "embedding": [/* 256 floats */],
      "preview_path": "clip-speakers/speaker_0_preview.wav",
      "library_matches": [
        {"name": "Crofty", "cosine": 0.83, "tier": "HIGH"},
        {"name": "Brundle", "cosine": 0.41, "tier": "LOW"}
      ]
    }
  ]
}
```

The cache fingerprint is `(source.sha256, source.mtime,
yipyap_version, schema_version, tooling.*)` — any change invalidates
the artifact and triggers re-ingest.

### `clip.speakers.json`

Two states. **Pre-label** (generated by ingest, ready for human edit):

```json
{
  "clusters": [
    {
      "cluster_id": 0,
      "label": "Crofty",
      "proposed_from": "library:HIGH",
      "preview_path": "clip-speakers/speaker_0_preview.wav"
    },
    {
      "cluster_id": 1,
      "label": null,
      "proposed_matches": [
        {"name": "Brundle", "cosine": 0.62, "tier": "MID"}
      ],
      "preview_path": "clip-speakers/speaker_1_preview.wav"
    }
  ]
}
```

**Post-label** (rewritten by label stage after validation): every
original cluster_id from the ingest artifact must appear exactly once
here, with one of four dispositions. Render reads this file and
resolves each ASR word's original cluster_id deterministically:

```json
{
  "labeled_at": "2026-05-16T21:50:00Z",
  "clusters": [
    {"cluster_id": 0, "disposition": "label", "label": "Crofty"},
    {"cluster_id": 1, "disposition": "label", "label": "Brundle"},
    {"cluster_id": 2, "disposition": "ignore", "reason": "PA announcer"},
    {"cluster_id": 3, "disposition": "merge_with", "target_cluster_id": 0},
    {"cluster_id": 4, "disposition": "split",
     "ranges": [
       {"start_s": 100.0, "end_s": 130.0, "label": "Crofty"},
       {"start_s": 130.0, "end_s": 160.0, "label": "Brundle"}
     ]}
  ]
}
```

Special fields the user can set in the pre-label file:

- `"ignore": true` — exclude this cluster from rendering (PA, noise).
- `"merge_with": 2` — collapse this cluster into cluster 2 before
  library write. Use when diarization over-split one speaker.
- `"split": {...}` — divide this cluster's turns by time range. Use
  when diarization under-merged. Less common; defer to v2 of the
  schema if hairy.

### Library profile (`~/.yipyap/speakers/crofty.json`)

```json
{
  "name": "Crofty",
  "created_at": "2026-05-16T21:50:00Z",
  "embedding_centroid": [/* 256 floats, recomputable from contributions */],
  "contributions": [
    {
      "clip_sha256": "abc123...",
      "clip_path": "abu_dhabi_60-90.mp4",
      "cluster_id": 0,
      "n_utterances": 312,
      "embedding": [/* 256 floats */],
      "added_at": "2026-05-16T21:50:00Z"
    }
  ],
  "voice_bank": "josh-m2",
  "pitch_adjust_st": 0.0,
  "jitter_st": 0.5,
  "yelling_threshold_dbfs": -12.0,
  "subtitle_color_hex": "#ffe680",
  "notes": "Sky F1 lead commentator. High excitement at race starts."
}
```

The `embedding_centroid` is the mean of `contributions[*].embedding`.
Storing both per-contribution and the centroid is intentional
redundancy — the centroid is what matching reads, the contributions
are what survive a misassignment rollback (see Library Hygiene).

## CLI surface

The current `yipyap input output` shape can either compose to the new
pipeline (auto-run ingest → auto-label-if-all-HIGH → render) or be
replaced by explicit subcommands. The explicit version is more honest
about the work happening:

```sh
# one-time setup
yipyap init                               # ~/.yipyap/{speakers,banks,config.toml}
yipyap banks list                         # show installed voice banks
yipyap banks install josh-default         # extracts the 8 josh voices

# per-clip flow
yipyap ingest clip.mp4                    # heavy: separation+ASR+diarize+embed
yipyap label clip.mp4                     # opens sidecar in $EDITOR (or TUI later)
yipyap render clip.mp4 out.mp4            # fast: synth + mix from cached artifacts

# composed convenience (for the simple case) — explicit confirmation step
yipyap clip.mp4 out.mp4                   # = ingest + label + render, with the
                                          # label step always run (one keypress
                                          # per cluster if all HIGH; full review
                                          # if any MID/LOW). Never silently
                                          # writes to the library.

# library management
yipyap speakers list                       # name, contributions, voice_bank
yipyap speakers show Crofty                # full profile
yipyap speakers rename "Speaker 0" Crofty  # cross-clip back-fill
yipyap speakers merge tmp_3 Crofty         # collapse duplicate (e.g. mislabel)
# un-poison after a misassignment (comment moved off the continuation line
# so the shell actually treats this as one command):
yipyap speakers remove-contribution \
    Crofty \
    --clip abu_dhabi_60-90.mp4 \
    --cluster 0
yipyap speakers delete Crofty              # nuclear option

# inspection
yipyap status clip.mp4                     # what's cached, what's stale
```

Defaults: `yipyap clip.mp4 out.mp4` never bypasses the label stage.
Even on an all-HIGH clip, the user is asked to confirm the proposed
labels — a one-keypress confirmation in the typical case, but the
confirmation event is what writes contributions into the library.
Writing to the library is never silent — a false-HIGH match would
otherwise poison the matched profile before the user saw it. If you
want to short-circuit even the keypress, `--auto-confirm-high` is the
explicit opt-in, and it logs every auto-accepted assignment so a bad
write is recoverable from the log.

## Failure modes and what they look like

The unsupervised setting has quiet failure modes that supervised
classifiers don't have. Worth enumerating so we design around them:

### Diarization over-split (one speaker as two clusters)

Symptom: Crofty's voice appears in cluster 0 AND cluster 5 in the
sidecar. Both might score HIGH against Crofty's library profile.

Workflow handle: user sets `"merge_with": 0` on cluster 5 in the
sidecar. Label stage merges before library write, only one
contribution lands.

### Diarization under-merge (two speakers as one cluster)

Symptom: cluster 0's preview clearly has two distinct voices. Library
match is LOW because the embedding is averaged across two people.

Workflow handle: user sets `"split"` with time ranges (or
`"ignore": true` and re-runs ingest with a different diarization
threshold, if that knob is exposed). Less common case; may need a
v2 schema iteration.

### Misassignment poisons the library

Symptom: user labeled cluster 0 as "Crofty" but it was actually
Martin. Crofty's centroid is now drifted. Future clips might match
wrong.

Workflow handle: `yipyap speakers remove-contribution Crofty --clip
clip1 --cluster 0`. The contribution is removed from the list,
centroid is recomputed from the survivors, future matches recover.
The audit trail in `contributions[]` makes this a one-command fix
instead of starting over.

### Embedding drift over many clips

Symptom: as Crofty's profile accumulates contributions, its centroid
drifts away from its original embedding. If broadcast channels change
(podcast appearance vs broadcast booth), the drift might break old
matches.

Workflow handle: explicit visibility (`speakers show` lists per-
contribution embedding distances from the centroid). If the centroid
spread gets pathological, the user can split the profile into
"Crofty-broadcast" / "Crofty-podcast" by selectively removing
contributions. Not a frequent operation but it needs to be possible.

### Embedding model is wrong for the audio

Symptom: cosine similarities are uniformly low (everyone reads as
"different speaker"). Library can never be built.

Workflow handle: this is a tooling problem, not a workflow one. The
proposed spike (see "Pre-adoption work" below) tests this before we
commit to the workflow. If pyannote/ECAPA can't separate F1
commentators cleanly, the whole workflow is on sand.

### Cold-start fatigue

Symptom: first clip has all-LOW matches (empty library), so the user
labels every cluster from scratch. Same on clip 2. Clip 3 starts
auto-matching but the user has already given up.

Workflow handle: explicit expectations setting. The README / `init`
output should tell the user "the first 2–3 clips do the heavy lifting
on labeling; subsequent clips are mostly confirmations." A bulk-
import command for known voices (`yipyap speakers import-known
crofty.wav --name Crofty`) gives a way to pre-seed if the user has
solo-voice samples available.

## Library hygiene as a first-class feature

A summary of the hygiene operations the workflow needs to support so
the library stays trustworthy:

| Operation                | When you need it                                       | CLI                                                  |
|--------------------------|--------------------------------------------------------|------------------------------------------------------|
| List profiles            | Routine inspection                                     | `yipyap speakers list`                               |
| Inspect a profile        | Audit which clips trained it                            | `yipyap speakers show Crofty`                        |
| Rename across clips      | "Speaker 3" → "Brundle" everywhere                      | `yipyap speakers rename "Speaker 3" Brundle`         |
| Merge profiles           | Two profiles are actually the same person               | `yipyap speakers merge tmp_3 Crofty`                 |
| Remove a contribution    | Un-poison after a misassignment                         | `yipyap speakers remove-contribution ...`            |
| Delete a profile         | Profile was created in error                            | `yipyap speakers delete Crofty`                      |
| Split a profile          | Centroid drift across channels                          | (deferred to schema v2)                              |
| Backup / restore         | Don't lose the library                                  | `yipyap speakers export libfile.tar.gz`              |

Backup matters: the library represents accumulated user effort. A
one-command export/import makes it portable across machines and
robust to accidental rm.

## Where ASR text fits

ASR is part of ingest, but its text output has multiple downstream
consumers:

1. **Animalese letter selection** (already used) — the synthesizer
   maps each transcribed letter to a sample.
2. **Speaker-cluster auxiliary cue** — top-5 transcribed words per
   cluster help the user recognise familiar phrasing during labeling.
3. **Subtitle overlay text** (if/when video lands) — the actual
   on-screen text in the AC-style text-box matches the ASR
   transcript, prefixed with the speaker label.

Implication: the ASR transcript needs to be high enough quality to
serve subtitle duty, not just letter-selection duty. faster-whisper
large-v3-turbo is already adequate per the V1 render telemetry.
Initial prompts matter — F1 commentary needs driver names primed
("Verstappen", "Pérez", "Hamilton") to avoid spelling mangles in
subtitles. The existing `--asr-prompt` flag already supports this.

## Letter-level timing for the eventual overlay

`render` produces `clip.render.json` with per-letter timing. The
overlay phase (if it lands) reads this. Schema sketch:

```json
{
  "words": [
    {
      "text": "Verstappen",
      "speaker": "Crofty",
      "start_s": 1.20,
      "end_s": 1.85,
      "letters": [
        {"char": "V", "start_s": 1.200, "end_s": 1.265},
        {"char": "e", "start_s": 1.265, "end_s": 1.330},
        ...
      ]
    }
  ]
}
```

The overlay renderer reveals one character on-screen exactly when
its animalese sample plays. They're driven by the same schedule, so
audio and video can never drift. Phrase-level breaks (text-box
transitions) come from ASR segment boundaries or speaker turns,
whichever ends sooner.

## CLI ergonomics — small details that matter

A few small choices that compound:

- **`$EDITOR` for label**: respect `$EDITOR`; default to `vi`. Don't
  build a TUI yet. The JSON contract is the durable thing; a future
  TUI just renders the same artifact.
- **`yipyap status clip.mp4`**: always available, never stale. Tells
  the user what stages have run, what's cached, what's missing. The
  "where am I in this flow" question must be one command away.
- **Dry-run flags**: `yipyap render --dry-run` shows the speaker
  assignments and voice-bank picks without actually rendering audio.
  Saves "render → listen → realize the wrong voice → re-render" loops.
- **Provenance in artifacts**: every JSON includes the yipyap version
  that produced it and a hash of its inputs. Stale-cache detection
  works automatically; bug reports become reproducible.
- **`--keep-temp`**: per Phase 3 of `ROADMAP.md`. Already planned;
  carries over.

## UI assumptions and the substrate/interaction split

A separate concern from the workflow logic, and one this document has
to be honest about because the draft above quietly assumed a UI without
saying so.

### Principle: the substrate is UI-independent, the interaction layer is not

The durable layer — artifact schemas, the ingest/label/render state
machine, the library structure, cache invalidation, the embedding +
matching operations — is portable across any UI. Any front-end is a
view onto this layer. We should design the substrate so a TUI or
visual UI can come later without re-architecting.

The *interaction layer* — how labeling actually happens, what
granularity of operation is reasonable, what feedback loops are tight
enough to iterate inside — depends on UI affordances. Pretending it
doesn't produces designs that secretly assume one UI and break under
another. The current draft has CLI / JSON-edit assumptions baked in.
Naming them rather than hiding them.

### Per-stage UI assumptions in the draft above

| Stage   | Current assumption (CLI / JSON-edit)                          | What changes under TUI                                   | What changes under visual UI (web/native)                |
|---------|---------------------------------------------------------------|----------------------------------------------------------|----------------------------------------------------------|
| Ingest  | Long-running, prints status, output is files on disk          | Same, with progress bar + spinner                         | Progress UI + cancellation; otherwise identical          |
| Label   | Batch: edit JSON sidecar in `$EDITOR`, save, re-run           | Question loop per cluster ("y/n/rename/skip")             | Click-through-with-playback; visual confidence bars      |
| Merge   | Add `"merge_with": N` field, re-run label                     | Same field, or prompt at confidence-tier boundary         | Drag-to-merge or shift-click; clusters visible as cards  |
| Split   | Deferred to schema v2 because hand-editing time ranges is awkward | Could prompt for `t0,t1` input pairs                  | **Drag a boundary on a waveform** — trivial natively     |
| Library | `yipyap speakers list / show` — CLI table                     | Same                                                      | Grid view with waveform thumbnails; cross-clip A/B       |
| Render  | `yipyap render`, output on disk                                | Same                                                      | Live preview + parameter tweaks before commit             |

Two of these are particularly UI-sensitive:

- **Split** is "deferred to v2" in the schema not because it's
  technically hard but because hand-editing time ranges is a bad UX
  for a non-rare operation. Under any visual UI it stops being
  deferred — it's just "drag the split point." So the deferral is a
  UI artifact, not a technical one. Worth flagging so future UI work
  knows this is low-hanging fruit.
- **Library browsing** scales differently. CLI list is fine at 10
  speakers, terrible at 100. The plan's library design doesn't assume
  100, but if it ever extrapolates that far the visual-UI ceiling
  arrives sooner than the CLI's.

There are also operations the draft doesn't mention because they don't
fit CLI well — "play 30 seconds of Crofty across three different clips
back-to-back to check the profile coheres" is one click in any visual
tool and a multi-command shell script in CLI. Their absence from this
plan is itself a UI assumption.

### The UI question is deferred, deliberately

VISION currently says *"No web UI, hosted service, or anything beyond
a local CLI."* That precludes one class of solutions before we've
measured whether the CLI / JSON-edit interaction is bearable. Three
postures the project can take:

| Posture                        | Cost                                  | What we give up                                                |
|--------------------------------|---------------------------------------|----------------------------------------------------------------|
| **A. CLI + JSON-edit only**    | Free (the draft's current shape)      | Cold-start labeling pain; awkward merge/split; library ceiling |
| **B. CLI + TUI for label**     | Real engineering investment, text-mode| Some UX wins (question-loop labeling); still no visual split   |
| **C. CLI + local-only web UI** | Bigger investment + VISION revision   | Substrate work is same; UI layer is heavier; richest UX        |

The right time to choose is **after the first labeling experience**,
not now. Build (A) as the v1 interaction layer; if it's painful enough
to abandon, upgrade to (B) or (C) with usage data in hand. The
substrate work is identical across the three, so this deferral has no
cost on the implementation side — only on the question of how much
friction the user (you) is willing to tolerate.

### What this means for the schema

The contracts in this document are deliberately written without UI
verbs. `clip.speakers.json` doesn't say "user clicks" or "user types"
— it says what the artifact contains and what state it represents.
Any UI is a function from artifact-state → screen + screen → artifact-
state. Schemas should keep that property as they evolve: if a future
field reads like "what the UI did" rather than "what is true about
the data," it's the wrong shape.

### Open UI questions, tracked but not yet decided

- Is the first labeling pass painful enough on real F1 clips to
  motivate a TUI? (Answer: try the embedding spike + label one clip
  by hand, then decide.)
- Do we want a `yipyap play <speaker>` cross-clip listening command
  as a CLI-side workaround for "browse the library by ear"? Cheap to
  add, no UI overhaul needed.
- If a visual UI ever happens, does it ship with yipyap or stay
  separate (`yipyap-studio`)? Composition story matters less than
  whether the substrate stays portable.

## What VISION.md needs to revise before this plan is adoptable

This plan contradicts the current `VISION.md` in three concrete ways.
Each is a deliberate change that needs the doc updated, not
in-passing drift:

1. **"`yipyap input.mp3 output.mp3` produces an output file"** (success
   criterion 1). The new shape is multi-command (`ingest / label /
   render`) with a composed-convenience shortcut. VISION should either
   keep the one-line invocation as a *composed* convenience over the
   subcommands, or replace the success criterion. Recommendation: keep
   as convenience, document the subcommand surface as the canonical
   shape.

2. **"Multi-speaker diarization" listed as a non-goal.** This plan
   makes diarization core. Recommendation: drop the non-goal, rewrite
   it to specify what we *do* support (cluster + label + persist),
   what we *don't* (real-time disambiguation, voice cloning of named
   speakers).

3. **State on disk.** VISION implies statelessness; this plan introduces
   `~/.yipyap/{speakers,banks,config.toml}` as durable state.
   Recommendation: add a "State" section to VISION.

Notably *not* changing VISION here: the video / overlay scope. The
labeling workflow stands on its own as an audio-only feature — speaker
labels surface in the rendered audio's voice mapping, even without a
text-box overlay. The overlay is a downstream consumer of the same
state, but its scope decision is independent.

## Pre-adoption work (before this plan becomes load-bearing)

Two things to do before any code lands against this plan:

### 1. Speaker-embedding spike

Test the technical premise. Pick two F1 clips with overlapping
commentators (e.g. Abu Dhabi + Monaco). For each: extract voice stem,
diarize, compute per-cluster embeddings using two backends
(`pyannote/wespeaker-voxceleb-resnet34-LM` and SpeechBrain
ECAPA-TDNN). Compute cross-clip cosine similarity matrices. Verdict
goes in `spikes/03-speaker-id-research.md` (companion to the v2
synthesis docs).

Cost: ~half a day. De-risks the whole plan — if embeddings don't
separate F1 commentators cleanly with reasonable thresholds, the
workflow above is built on sand and the design needs to be different.

Predicted outcome (so a mismatch is informative): same-speaker cos
> 0.7, different-speaker < 0.45, threshold gap of ~0.25 between HIGH
and LOW tiers gives clean tier assignment. If the gap is < 0.1 the
tiering scheme collapses and we need a different matching strategy.

### 2. VISION revision PR

Three concrete edits to `VISION.md` (see section above). Land as one
PR before any workflow code merges. Reviewers (you, reading it cold)
should be able to verify the plan and the VISION agree.

### 3. (Optional) Audit `02_synthesis.py` for what carries over

The existing `cluster_speakers_by_pitch` and `assign_words_to_speakers`
in `02_synthesis.py` are anonymous-cluster-shaped; they survive into
the ingest stage as fallback or first-pass diarization but are not
embedding-aware. Worth a short note in the ingest implementation plan:
keep them as a debug/CPU-only path, prefer pyannote when available.

## Concrete next steps (pick one)

1. **Run the embedding spike** (Pre-adoption work item 1) — half a
   day, validates the design's core premise.
2. **Revise VISION.md first** (Pre-adoption work item 2) — small
   doc PR, lets us proceed without drift.
3. **Both, in sequence** — VISION revision is small, embedding spike
   benefits from VISION already being explicit about diarization being
   in scope.

I'd lean (3), do the VISION edit today, run the spike next.

## Companion documents (not yet written)

- `spikes/03-speaker-id-plan.md` — the spike plan that produces the
  embedding-stability verdict.
- `spikes/03-speaker-id-research.md` — that spike's findings.
- `docs/architecture.md` "Decisions deferred" — sample source + ASR
  vs onset path + pitch tracker still open; landing them is part of
  closing Phase 0 cleanly.

These exist as anchors; this document doesn't depend on them being
written, but the next code PRs will.
