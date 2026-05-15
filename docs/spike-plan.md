# Phase 0 — Spike Plan

Two spikes, both throwaway, both required before any Phase 1 PR lands. Outputs are
listening verdicts and a short findings doc, not production code.

---

## Spike A — Source separation on sports audio

**Question:** Can off-the-shelf separation models cleanly split a real sports clip into
"voice" and "everything else"? Specifically, can we get a no-voice stem clean enough
that we can swap the voice without ghost speech bleeding through, and a voice stem
clean enough to analyze?

**Method:**
1. Pick one real source clip (~30s of commentary with audible crowd, music, transitions).
   Stored locally only — not committed.
2. Run separation with at least two models:
   - Demucs `htdemucs_ft` (vocals stem)
   - Demucs `mdx_extra` *or* MDX-Net
   - (Optional) one speech-enhancement model for comparison, e.g. DeepFilterNet
3. Listen to both stems from each model. Note:
   - Bleed of crowd/music into the voice stem (how much, how distracting).
   - Bleed of commentary into the no-voice stem (how much speech you can still hear).
   - Artifacts (warbling, swirling, dropouts).
4. Note runtime per minute of input on CPU.

**Decision:**
- If at least one model gives both stems "good enough" (subjective — but the no-voice
  stem must not have intelligible speech under it), pick that model and proceed.
- If none are acceptable, the project may need a different strategy (e.g., gate the
  whole voice region rather than replace it). Stop and reconvene.

**Deliverable:** A paragraph in `spikes/findings.md` (local-only) recording: clip used,
models tried, runtime, verdict per stem per model, chosen model.

---

## Spike B — Onset-aligned animalese

**Question:** When we drive an animalese sample bank from onset detection + pitch
tracking on the isolated voice stem, does the result sound like animalese over the
original cadence, or does it sound like noise?

**Method:**
1. Use the voice stem from Spike A.
2. Run VAD (webrtcvad or silero-vad) → voiced regions.
3. Inside voiced regions, run onset detection (librosa.onset.onset_detect).
4. At each onset, estimate pitch (librosa.pyin or CREPE).
5. Build a tiny animalese sample bank — 5–10 short pitched syllable samples. Generate
   them quickly (sine + envelope, or pull from an existing animalese.js port).
6. At each onset time, pick a random sample, pitch-shift it to the detected pitch, place
   it. Length capped to time-until-next-onset.
7. Render to a wav. Listen.

**Decision:**
- If you can hear the cadence of the commentary and the result feels like animalese:
  proceed with the onset path in Phase 1.
- If onsets are too dense, too sparse, or rhythm doesn't track: try one fix
  (filter onsets by energy threshold). If still bad: switch to transcription-based
  fallback for Phase 1.
- If samples sound bad even with good timing: revisit the sample bank design before
  Phase 1 (different base samples, different pitch-shift method).

**Deliverable:** Two output wavs and a paragraph in `spikes/findings.md`:
- `spike-b-onset-direct.wav` — just animalese, no background.
- `spike-b-mixed.wav` — animalese mixed onto Spike A's no-voice stem.
- Verdict and recommended path for Phase 1.

---

## Working directory for spikes

```
~/Development/yipyap/spikes/        # gitignored except README and .py files
  README.md                          # the checklist below
  01_separation.py                   # script for Spike A
  02_synthesis.py                    # script for Spike B
  inputs/                            # local source clips (gitignored)
  output/                            # generated wavs (gitignored)
  findings.md                        # local-only notes (gitignored)
```

`spikes/*.py` scripts are tracked. Inputs, outputs, and findings are local.

## Checklist

- [ ] Source clip(s) selected and placed in `spikes/inputs/`.
- [ ] Spike A run with two separation models. Verdict written.
- [ ] Spike B run on Spike A's chosen voice stem. Verdict written.
- [ ] Decisions recorded back into `docs/architecture.md` ("Decisions deferred"
      section).
- [ ] `spikes/findings.md` summarized into a short note in `docs/listening-log.md` once
      that file exists in Phase 1.

## What NOT to do during spikes

- Don't build modules. Don't create a CLI. Don't write tests.
- Don't commit audio. Don't commit findings.
- Don't tidy the spike code "for re-use." It's throwaway.
- Don't proceed to Phase 1 PRs until both verdicts are written.
