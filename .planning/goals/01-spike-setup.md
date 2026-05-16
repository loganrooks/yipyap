---
status: done
created: 2026-05-15
fired: 2026-05-15
phase: Phase 0
summary: Stand up the spike scaffold (scripts, deps, gitignore) so spikes are runnable end-to-end on synthetic input. No real source clip required at this stage; no listening verdicts written.
depends-on: none
outcome: Met. spikes/{README.md, requirements.txt, 01_separation.py, 02_synthesis.py, findings.md, inputs/, output/} created; .venv-spikes/ provisioned with demucs 4.0.1, torch 2.12.0, librosa 0.11.0, silero-vad 6.2.1; both scripts run end-to-end on a 5s synthetic clip with exit 0. htdemucs_ft ran ~1.25× realtime on CPU.
notes:
- demucs 4.0.1 has no demucs.api module — used demucs.pretrained.get_model + demucs.apply.apply_model.
- torchaudio 2.11 now requires torchcodec for save — switched to soundfile.write directly.
- silero-vad classified the synthetic sine as non-speech (0 voiced regions), so the synthesis path produced silence on smoke. That's expected behavior; on a real commentary clip the path activates.
---

```
/goal Set up Phase 0 spike scaffold per docs/spike-plan.md. End state: infrastructure runnable end-to-end on a synthetic placeholder input. No real source clip needed for this goal.

COMPLETE WHEN ALL TRUE:

1. SCAFFOLD — spikes/ contains: README.md reproducing the spike-plan.md checklist plus invocation docs; requirements.txt pinning spike-only deps installed into a fresh .venv-spikes/ (gitignored); findings.md as a local-only template stub with TODO placeholders for both spike verdicts.

2. SCRIPT 01 — spikes/01_separation.py is a single-file script implementing Spike A per docs/spike-plan.md: Demucs separation on a path arg with at least two models (htdemucs_ft + mdx_extra), writes stems to spikes/output/spike-a/<model>/<clip-stem>/{voice,background}.wav, prints per-model runtime and runtime-per-minute estimate.

3. SCRIPT 02 — spikes/02_synthesis.py is a single-file script implementing Spike B per docs/spike-plan.md: given a voice stem path, runs VAD → onset detection (librosa) → pitch tracking (librosa.pyin) → animalese sample fire, writes spikes/output/spike-b/spike-b-onset-direct.wav. If passed an optional background stem path, also writes spike-b-mixed.wav.

4. SMOKE — both scripts execute end-to-end on a generated synthetic input (e.g., 5-second sine+noise tmpfile) without raising. Surface exit codes and produced file lists in the transcript.

5. GITIGNORE — spikes/inputs/, spikes/output/, spikes/findings.md, .venv-spikes/, and audio extensions under spikes/ are all ignored. Confirm with `git check-ignore -v` on representative paths.

6. CLEAN TRACKING — `git status` shows only intended files (.py scripts, README.md, requirements.txt, any .gitignore edits). No audio, no findings.md, no venv tracked.

CONSTRAINTS (do not violate):
- Do NOT modify pyproject.toml, VISION.md, ROADMAP.md, docs/architecture.md, or docs/pr-plan.md. Spike setup is independent of those.
- Do NOT create src/yipyap/ or any project module. Throwaway scripts under spikes/ only.
- Do NOT write tests.
- Do NOT git commit — stage with `git add` only. Commits require explicit approval.
- Do NOT write listening verdicts in findings.md — those come from a human listening pass.
- Do NOT run on a real source clip from spikes/inputs/ — that's a separate goal.
- If a Demucs model download or dep install fails repeatedly (>2 attempts on the same item), STOP and report instead of looping. Do not silently swap libraries on platform/install failures.

EVIDENCE TO SURFACE BEFORE CLAIMING DONE:
- `find spikes/ -maxdepth 2 -not -path '*/\.*'`
- `cat spikes/requirements.txt`
- Both scripts' synthetic-input run output (exit code + produced files)
- `git status`
- `git check-ignore -v spikes/inputs/x.wav spikes/output/y.wav spikes/findings.md`

BOUND: stop after 30 turns. If blocked on environment setup for 3+ consecutive turns, stop and report.
```
