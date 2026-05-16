# Phase 0 spikes — scaffold

Throwaway code. The point of this directory is to answer two listening questions
before Phase 1 starts. See `docs/spike-plan.md` for the rationale.

## What lives here

```
spikes/
  README.md                # this file — checklist + invocation
  requirements.txt         # spike-only deps (NOT project deps)
  01_separation.py         # Spike A — source separation
  02_synthesis.py          # Spike B — onset-aligned animalese
  inputs/                  # gitignored: drop source clips here
  output/                  # gitignored: scripts write stems / synthesis here
  findings.md              # gitignored: human listening verdicts go here
```

Only `README.md`, `requirements.txt`, `01_separation.py`, and `02_synthesis.py`
are committed. Everything under `inputs/`, `output/`, plus `findings.md` and
`.venv-spikes/` are local-only.

## Setup (one-time)

```sh
python3.11 -m venv .venv-spikes
source .venv-spikes/bin/activate
pip install --upgrade pip
pip install -r spikes/requirements.txt
```

The first run of Spike A will pull Demucs model weights (a few hundred MB per
model, cached under `~/.cache/torch/hub`).

## Spike A — Source separation

Question: can off-the-shelf separation cleanly split a sports clip into voice
and "everything else"? Per `docs/spike-plan.md`, we run **three
architecturally distinct methods** — not just multiple Demucs variants — so
the verdict reflects cross-family signal:

```sh
# (1) Demucs family (hybrid transformer / MDX) — default backend.
python spikes/01_separation.py spikes/inputs/your-clip.mp3
# Runs htdemucs_ft and mdx_extra by default.
python spikes/01_separation.py spikes/inputs/your-clip.mp3 \
  --backend demucs --models htdemucs_ft mdx_extra

# (2) Open-Unmix (Bi-LSTM masking on spectrograms).
python spikes/01_separation.py spikes/inputs/your-clip.mp3 \
  --backend umx --models umxl

# (3) MDX-Net via audio-separator (UVR).
python spikes/01_separation.py spikes/inputs/your-clip.mp3 \
  --backend mdx --models UVR-MDX-NET-Inst_HQ_3.onnx
```

Writes `voice.wav` and `background.wav` under
`spikes/output/spike-a/<backend>-<model>/<clip-stem>/` for each model and
prints a runtime-per-minute estimate. The `<backend>-<model>` prefix keeps
the listening matrix unambiguous when you compare across families.

Listen to:

- The voice stem — is crowd/music bleed acceptable for downstream analysis?
- The background stem — is residual commentary intelligible? (It must not be.)

### Trying DeepFilterNet (optional)

DeepFilterNet is a **speech-enhancement** model, not a separator: it produces
an enhanced voice and an implicit (by subtraction) background, which is a
different operational mode. It is **not** required for Spike A — only reach
for it if the three required methods are inconclusive.

```sh
# Install in the spike venv only; not in spikes/requirements.txt.
pip install deepfilternet

# Minimal one-shot enhancement (writes <name>_DeepFilterNet3.wav alongside input):
python -c "from df.enhance import enhance, init_df, load_audio, save_audio; \
import torch, sys; model, df_state, _ = init_df(); \
audio, _ = load_audio(sys.argv[1], sr=df_state.sr()); \
save_audio(sys.argv[1].replace('.wav','_DeepFilterNet3.wav'), \
enhance(model, df_state, audio), df_state.sr())" spikes/inputs/your-clip.wav
```

## Spike B — Onset-aligned animalese

Question: driven from VAD + onsets + pitch on the voice stem, does the
animalese track follow the commentary's cadence? Per `docs/spike-plan.md`,
this is split into three sub-tests so cadence and timbre failures stay
diagnosable.

```sh
# (1) Cadence test — inline sine bank, ugly by design. Listen for rhythm only.
python spikes/02_synthesis.py \
  spikes/output/spike-a/htdemucs_ft/your-clip/voice.wav
# → spikes/output/spike-b/spike-b-cadence.wav

# (2) Timbre test — real animalese bank, no background. Listen for whether the
# samples sound right.
python spikes/02_synthesis.py \
  spikes/output/spike-a/htdemucs_ft/your-clip/voice.wav \
  --samples-dir spikes/samples/
# → spikes/output/spike-b/spike-b-real.wav

# (3) Combined verdict — real bank + Spike A background. Closest to the
# eventual listening experience.
python spikes/02_synthesis.py \
  spikes/output/spike-a/htdemucs_ft/your-clip/voice.wav \
  spikes/output/spike-a/htdemucs_ft/your-clip/background.wav \
  --samples-dir spikes/samples/
# → spikes/output/spike-b/spike-b-real.wav AND spike-b-real-mixed.wav
```

Real animalese banks are pitched up. If the default mapping pulls samples
into muddy bass, add `--pitch-offset 12` (one octave up) — see the
"Known knobs / non-failures" subsection of `docs/spike-plan.md`.

`spikes/samples/` is gitignored — the upstream `animalese.wav` is from
`acedio/animalese.js` and we don't redistribute it, only the slicer that
regenerates the bank. To populate it on a fresh checkout:

```
python spikes/00_extract_bank.py
```

That downloads the source WAV, slices it into 26 letters, peak-normalizes
each to 0.95 with short edge fades, and writes `{a..z}.wav` (PCM_16,
0.15s, 44.1 kHz mono) into `spikes/samples/`. Pass `--out PATH` to extract
elsewhere, `--source PATH` to use a pre-downloaded WAV (offline / firewalled
hosts).

Output filenames are driven by the bank:

| Invocation                       | Direct output             | Mixed output                   |
|----------------------------------|---------------------------|--------------------------------|
| no `--samples-dir`               | `spike-b-cadence.wav`     | `spike-b-cadence-mixed.wav` *  |
| `--samples-dir spikes/samples/`  | `spike-b-real.wav`        | `spike-b-real-mixed.wav` *     |

*Mixed file is only written when a background stem is also passed.

## Listening protocol

Mirrored from `docs/spike-plan.md` — these spikes only matter if a human
listens carefully:

- **Spike A:** A/B the same 10s segment from both models back-to-back with
  eyes closed (no peeking at the model name). Repeat per clip. Aggregate the
  verdict across clips — don't decide from one sample.
- **Spike B:** listen once at **0.75× speed** first to catch alignment slips
  that mask at full speed, then again at full speed for the artistic
  judgement.

## Checklist (from `docs/spike-plan.md`)

- [ ] Source clip(s) selected and placed in `spikes/inputs/`.
- [ ] Spike A run with at least two separation models. Verdict written to
      `spikes/findings.md`.
- [ ] Spike B run on Spike A's chosen voice stem. Verdict written.
- [ ] Decisions recorded back into `docs/architecture.md` "Decisions deferred"
      section.
- [ ] Once `docs/listening-log.md` exists in Phase 1, summarise the findings
      there.

## What this scaffold deliberately does NOT do

- It is not a module. There is no package, no entry point, no API.
- It does not run on import. Both scripts are CLIs.
- It does not commit audio or findings — see `.gitignore` at the repo root.
- It does not write listening verdicts; those come from a human ear, recorded
  by hand in `findings.md`.
