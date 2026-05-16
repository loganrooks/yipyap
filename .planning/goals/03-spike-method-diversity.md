---
status: done
created: 2026-05-15
fired: 2026-05-15
phase: Phase 0
summary: Add architectural method diversity to Spike A. Replace the "two Demucs models" requirement with three architecturally distinct methods (Demucs + Open-Unmix + MDX-Net via audio-separator) so the verdict reflects cross-family signal, not Demucs hyperparameter variance.
depends-on: 02-spike-revisions.md
outcome: |
  Met. docs/spike-plan.md Spike A method requires three architecturally
  distinct methods (Demucs family, Open-Unmix, MDX-Net via audio-separator);
  DeepFilterNet documented as optional fallback. Deliverable + Decision wording
  shifted from "model" → "method"; cross-family disagreement explicitly
  flagged as signal. spikes/requirements.txt now installs
  `audio-separator[cpu]>=0.18` and `openunmix>=1.2.1`; numpy upper pin removed
  (audio-separator pulled numpy 2.4.5 transitively; librosa 0.11 + demucs 4.0.1
  + silero-vad + openunmix all import OK on numpy 2). 01_separation.py
  refactored to multi-backend with `--backend {demucs,umx,mdx}` and per-backend
  default models; outputs now under `<backend>-<model>/<clip-stem>/`. README.md
  shows all three backend invocations + opt-in DeepFilterNet section.
  findings.md template updated with method × clip verdict matrix, Demucs
  within-family agreement sub-rows, and a cross-family commentary section.
  All four smoke runs landed:
    (i)  demucs/htdemucs_ft   → exit 0, ratio 1.35× realtime
    (ii) umx/umxl             → exit 0, ratio 7.83× (incl. ~432MB weight download)
    (iii) mdx/UVR-MDX-NET-Inst_HQ_3.onnx → exit 0, ratio 1.22× (incl. 66.8MB download)
    (iv) umx/bogus_model error → exit 1 with stderr
       "AttributeError: module 'openunmix' has no attribute 'bogus_model'"
  Chosen MDX-Net default: UVR-MDX-NET-Inst_HQ_3.onnx (audio-separator catalogue
  ranks it vocals SDR ~8.8 — strong vocal-isolation MDX-Net variant).
  Goal-02 revisions (Spike B split, multi-clip, listening protocol, Spike B
  knobs) preserved intact. openunmix.predict.separate signature unchanged:
  `(audio, rate=None, model_str_or_path='umxl', targets=None, niter=1,
  residual=False, ...)` — residual=True still works as documented.
  Staged only (no commit).
notes:
- Initial goal text named `python-audio-separator` — that's the GitHub repo name; the PyPI distribution is `audio-separator`. Used the correct PyPI name.
- audio-separator install upgraded numpy 1.26.4 → 2.4.5. All other spike deps still import cleanly on numpy 2.
- Smoke ratio for umx is inflated by weight download in the same run; on cached weights it should be much closer to demucs's 1.x ratio.
- The umx backend's bogus-model error surfaces as an AttributeError (openunmix loads models via attribute lookup on its package); message is still clear and exits non-zero.
rationale: |
  Current plan biases toward "two Demucs models" — different training recipes
  within the same architecture family. That is Demucs hyperparameter
  diversity, not method diversity.

  Open-Unmix uses Bi-LSTM masking — a genuinely different family — and is
  already installed transitively as a Demucs dep, so adding it is ~free.

  audio-separator exposes UVR's MDX-Net models, which are convolutional
  masking and often outperform Demucs on vocal isolation. One new pip dep.

  DeepFilterNet is a different paradigm — speech enhancement rather than
  source separation. Worth mentioning in the plan as a fallback path for
  Phase 1 if separation results are inconclusive, but not as a required
  Spike A method (it doesn't produce a true background stem, only a
  cleaned voice + implicit-by-subtraction background).
---

## Intent (full detail)

The current plan and scaffold ask "does separation work on sports audio?"
and answer it with two Demucs models. That's a within-family question: are
htdemucs_ft and mdx_extra agreeing because they're both correct, or because
they're both biased the same way?

Adding cross-family signal:

- **Demucs family** (htdemucs_ft + mdx_extra) — hybrid transformer / MDX
  training. Already installed and integrated.
- **Open-Unmix** (umxl) — Bi-LSTM masking on spectrograms. Architecturally
  unrelated to Demucs. Already in the venv as a transitive dep, so adding it
  is mostly a code task in `01_separation.py`.
- **MDX-Net via `python-audio-separator`** — convolutional masking; UVR's
  MDX-NET models often top vocal-isolation benchmarks. One new pip dep, one
  new model download.
- **DeepFilterNet** — speech enhancement, not separation. Documented as
  optional because it produces an enhanced voice and an implicit (by
  subtraction) background, which is a different operational mode. Worth a
  README pointer for users who want to try it if separation methods
  underperform.

### Why this matters for the verdict

Spike A's killer criterion is "the no-voice stem must not have intelligible
speech under it." Demucs and Open-Unmix were trained on music; "vocals" to
them is a singer, not a commentator. There's a domain mismatch that doesn't
show up unless we vary the architecture. If three families disagree, that's
useful signal. If two families agree and one dissents, the dissenter might
be revealing a specific limitation. If three families agree, the verdict is
robust.

### Backend refactor in `01_separation.py`

Add `--backend {demucs,umx,mdx}` with `demucs` as default to preserve the
invocations documented in README/findings from earlier goals. Output paths
gain a `<backend>-<model>` prefix so the listening matrix has clean per-cell
identifiers.

API specifics:

- **umx:** `openunmix.predict.separate(audio, model_str_or_path='umxl',
  targets=['vocals'], residual=True, device='cpu')`. Voice is
  `estimates['vocals']`; background is `estimates['residual']` (or sum of
  non-vocal stems if a four-target umxl is returned).
- **mdx:** `audio_separator.separator.Separator()` → `load_model(...)` →
  `separate(...)`. Output filenames map to voice/background by naming
  convention; the wrapper logs what filename the loaded model uses.

### DeepFilterNet (documented, not required)

README gets a short section: `pip install deepfilternet`, one-line example
that takes a path and writes an enhanced WAV. Not added to
`spikes/requirements.txt`. Not exercised by the goal smoke. Mentioned in the
plan as a fallback path for Phase 1 only if Spike A's separation verdict is
weak.

### Output naming change is a breaking change

Earlier goals produced `spikes/output/spike-a/<model>/<clip>/`. This goal
moves to `spikes/output/spike-a/<backend>-<model>/<clip>/`. Outputs are
gitignored so this is a local-only break — re-run on real clips after the
goal lands.

## /goal prompt (≤4000 chars)

```
/goal Add architectural method diversity to Spike A. Assumes goal 02 applied.

A. docs/spike-plan.md — revise Spike A method:
   - Replace the two-Demucs-models requirement with: "Run separation across at least three architecturally distinct methods:
     (1) Demucs family — htdemucs_ft and mdx_extra count together as one method.
     (2) Open-Unmix — umxl or umxhq.
     (3) MDX-Net via audio-separator — pick one strong UVR MDX-Net model.
     DeepFilterNet: OPTIONAL fallback if Spike A is inconclusive — speech enhancement, produces enhanced voice + implicit-by-subtraction background (different mode)."
   - Update the listening-verdict matrix to be method × clip (not model × clip).
   - Keep goal-02 revisions (multi-clip, Spike B cadence/timbre split, listening protocol) intact.

B. spikes/requirements.txt — add `python-audio-separator[cpu]>=0.18`. Leave DeepFilterNet out; document in README as opt-in (`pip install deepfilternet`).

C. spikes/01_separation.py — refactor to multi-backend:
   - --backend {demucs,umx,mdx} (default: demucs, preserves earlier README invocations).
   - --models semantics per backend: demucs takes Demucs names (default htdemucs_ft mdx_extra); umx takes umxl/umxhq (default umxl); mdx takes audio-separator model filenames (default: pick one current strong UVR-MDX-NET-Inst variant and log the choice).
   - Output structure: spikes/output/spike-a/<backend>-<model>/<clip-stem>/{voice,background}.wav.
   - umx backend: openunmix.predict.separate(..., residual=True); voice = estimates['vocals']; background = estimates['residual'] or sum of non-vocal stems.
   - mdx backend: audio_separator.separator.Separator with load_model + separate; map output filenames to voice.wav / background.wav.
   - Each backend logs runtime + per-minute estimate. Errors raised cleanly; no cross-backend silent fallback.

D. spikes/README.md — show invocations for all three backends. Add "Trying DeepFilterNet (optional)" section with pip command and one-line example. Keep goal-02 revisions intact.

E. spikes/findings.md — update template:
   - Method × clip matrix (rows = methods, columns = clips, cells = brief verdict + runtime per minute).
   - Cross-family commentary section: do disagreements suggest a single-method bias?
   - "Chosen method for Phase 1: TODO" with sub-fields; keep goal-02 fields intact.

SMOKE — verify on /tmp/yipyap_smoke.wav:
   (i) defaults (--backend demucs --models htdemucs_ft) → spikes/output/spike-a/demucs-htdemucs_ft/yipyap_smoke/{voice,background}.wav, exit 0.
   (ii) --backend umx --models umxl → spike-a/umx-umxl/... , exit 0.
   (iii) --backend mdx --models <chosen MDX-Net filename> → spike-a/mdx-<model>/... , exit 0.
   (iv) error: --backend umx --models bogus_model → non-zero exit with helpful stderr.
   Surface exit codes + file lists for all four.

CONSTRAINTS:
- Do NOT modify pyproject.toml, VISION.md, ROADMAP.md, docs/architecture.md, or docs/pr-plan.md.
- Do NOT undo goal-02 revisions (Spike B split, multi-clip, listening protocol).
- Do NOT modify spikes/02_synthesis.py beyond doc comments.
- Do NOT write tests or create src/yipyap/.
- Do NOT git commit. Staging only.
- Do NOT commit new audio (model weights, sample banks, smoke outputs).
- Do NOT make DeepFilterNet a hard requirement — README opt-in only.
- If audio-separator install fails after 2 attempts on this platform, STOP and report.
- If openunmix's residual-extraction API has changed, surface the API surface and STOP. No workarounds.

EVIDENCE:
- `git diff -- docs/spike-plan.md spikes/01_separation.py spikes/requirements.txt spikes/README.md spikes/findings.md`
- All four smoke runs (exit codes + produced files).
- `git status --short`
- The specific UVR-MDX-NET-* model filename chosen for the mdx backend's default.

BOUND: stop after 25 turns. If audio-separator install or a backend integration fails repeatedly (>2 attempts on the same root cause), STOP and report.
```
