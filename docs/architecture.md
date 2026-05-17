# Architecture

## Pipeline

```
            ┌──────────────┐    voice.wav     ┌──────────────┐    events       ┌────────────────┐
input.mp3 ─►│  Separator   │─────────────────►│   Analyzer   │────────────────►│  Synthesizer   │──┐
            │              │    background.wav│              │                 │                │  │
            │              │──────┐           └──────────────┘                 └────────────────┘  │
            └──────────────┘      │                                                                │
                                  │                                                       animalese.wav
                                  │                                                                │
                                  ▼                                                                ▼
                          ┌─────────────────────────────────────────────────────────────────────────┐
                          │                              Mixer                                       │
                          └─────────────────────────────────────────────────────────────────────────┘
                                                            │
                                                            ▼
                                                       output.mp3
```

Four pure-ish stages plus a thin CLI wrapper. Stages know nothing about each other
except their interface types.

## Module layout (Python)

```
src/yipyap/
  __init__.py
  cli.py              # argparse / entry point
  separator/
    __init__.py       # exports `separate(in_path, work_dir) -> SeparationResult`
    demucs_backend.py
  analyzer/
    __init__.py       # exports `analyze(voice_path) -> list[VoiceEvent]`
    vad.py
    onsets.py
    pitch.py
  synthesizer/
    __init__.py       # exports `synthesize(events, sample_bank) -> np.ndarray`
    sample_bank.py
    pitch_shift.py
  mixer/
    __init__.py       # exports `mix(animalese, background, ref_voice) -> np.ndarray`
    loudness.py
  io/
    __init__.py       # read/write helpers, working-dir lifecycle
tests/
  fixtures/
    short_commentary.wav  # ~10s, committed via git-lfs or small enough to commit raw
  test_separator.py
  test_analyzer.py
  test_synthesizer.py
  test_mixer.py
  test_pipeline.py
```

## Data shapes between stages

These are the contracts. Modules may change internals freely as long as inputs and
outputs match.

### `SeparationResult`

```python
@dataclass
class SeparationResult:
    voice_path: Path          # mono or stereo wav of isolated speech
    background_path: Path     # mono or stereo wav of everything else
    sample_rate: int
    duration_s: float
```

### `VoiceEvent`

One per detected syllable/onset in the voice stem.

```python
@dataclass
class VoiceEvent:
    time_s: float       # onset time, seconds from start
    duration_s: float   # how long this event holds (until next onset or end of voiced region)
    pitch_hz: float     # estimated f0 at the onset; 0 if unvoiced
    energy: float       # normalized 0..1 RMS at the onset
    voiced: bool        # whether this event falls inside a voiced region
```

`Analyzer.analyze` returns `list[VoiceEvent]` sorted by `time_s`. Unvoiced events may be
included (energy spikes that aren't speech) but `voiced=False` so the synthesizer can
skip them.

### Synthesizer output

A numpy array (`float32`, shape `(num_samples,)` for mono or `(num_samples, 2)` for
stereo) at the sample rate of the original input. Length equals the original voice
stem length so the mixer can align by start time.

### Mixer input

```python
def mix(
    animalese: np.ndarray,
    background: np.ndarray,
    ref_voice: np.ndarray,      # original voice stem, used for loudness reference
    sample_rate: int,
) -> np.ndarray
```

Returns the final mixed audio at the same sample rate as inputs.

## CLI shape (Phase 1)

```
yipyap INPUT OUTPUT
```

No flags in Phase 1. Phase 3 introduces flags per `ROADMAP.md`.

## Working directory

Each invocation creates a temp working dir (`tempfile.mkdtemp(prefix="yipyap-")`).
Intermediate files (voice stem, background stem, animalese before mix) live there.
Removed on success unless `--keep-temp` (Phase 3+).

## Sample rate handling

- Input is decoded to the model's preferred SR for separation (typically 44.1 kHz for
  Demucs).
- Analyzer, synthesizer, and mixer all operate at that SR.
- Output is re-encoded to match the original input's container/format where possible.

## Errors

- All public stage functions raise `YipyapError` (defined in `yipyap.errors`) with a
  human-readable message. The CLI catches it and prints to stderr.
- Internal exceptions (FileNotFound, decode errors) are wrapped, not propagated raw.

## Why this shape

- **Stages are pure functions of their inputs.** Easy to unit-test, easy for an agent to
  swap an implementation (e.g., Demucs → MDX-Net) without touching anything else.
- **`VoiceEvent` is the abstraction that decouples analyzer from synthesizer.** If we
  later need a transcription-based path, we still emit `VoiceEvent`s — just generated
  from phoneme timestamps instead of onset detection.
- **Mixer takes `ref_voice` separately** so loudness can be matched to the *original*
  speech rather than to the background, even when the background is much louder.

## Decisions deferred until Phase 0 findings land

- **Separation method (decided 2026-05-15, Spike A):** MDX-Net via
  `audio-separator`, default model `UVR-MDX-NET-Inst_HQ_3.onnx`. Auto-runs on
  ONNX Runtime's CoreML execution provider on Apple Silicon. Beat the Demucs
  family and Open-Unmix on background preservation across three F1 clips
  (clean engines, mid-race, podium-territory). Cross-family note in
  `spikes/findings.md`: MDX-style *training* matters more than Demucs-vs-MDX-Net
  *architecture* — Demucs's `mdx_extra` clustered with UVR's MDX-Net on
  background fidelity, not with its sibling `htdemucs_ft`. The Phase 1
  separator module will be `separator/mdx_backend.py` (replacing the
  `demucs_backend.py` placeholder in the layout above) and will keep the
  documented `separate(in_path, work_dir) -> SeparationResult` contract.
- **Analyzer driver (decided 2026-05-16, Spike B):** **ASR-driven**, not
  onset-driven. The original plan (`VISION.md`, `docs/spike-plan.md`) put
  onset+pitch first and listed transcription as a fallback. In practice
  the synthesis spike ended up running on `--asr-input` mode and the
  result was the path that produced audible quality (V1 of
  `spikes/02-synthesis-plan-v2.md`). The Phase 1 analyzer pipeline is
  ASR → diarization → per-word events, not onset → pitch → per-onset
  events. `VoiceEvent` is consequently the wrong contract shape; replace
  with `WordEvent { text, start_s, end_s, speaker_id, pitch_hz }` in
  Phase 1. Pitch tracking is still per-event, just keyed off ASR word
  boundaries instead of onsets.
- **ASR backend (decided 2026-05-16, Spike B):** faster-whisper
  `large-v3-turbo` for CUDA, mlx-whisper equivalent on Apple Silicon.
  Initial-prompt support is load-bearing — F1 commentary needs driver
  names primed ("Verstappen", "Pérez", "Hamilton") to avoid spelling
  mangles that propagate into both letter-selection and any future
  subtitle text. Already exposed as `--asr-prompt` in
  `spikes/02_synthesis.py`.
- **Pitch tracker (decided 2026-05-16, Spike B):** `librosa.pyin`.
  Used for both per-word pitch estimation on the voice stem and for
  bank-base-frequency estimation on loaded samples. CREPE / RMVPE were
  not needed; pyin is adequate at the per-word granularity ASR
  produces. Reconsider only if Phase 2 pitch smoothing requires
  finer-grained or more robust estimation.
- **Animalese sample source (decided 2026-05-16, Spike B):**
  **Pre-recorded sample bank.** The original acedio
  `animalese.wav` (PCM_U8, ~48 dB SNR, 26 letters at 0.15 s) was the
  starting substrate and turned out to be the perceptual ceiling — its
  quantization floor dominated audible static regardless of pipeline
  polish (see `spikes/02-synthesis-findings.md` 2026-05-16 (b) and
  (c)). Synthesized-base + pitch-shift was not pursued. The new
  substrate is `joshxviii/animalese-typing-desktop`'s 16-bit per-letter
  recordings, eight independently-recorded voices, 200 ms per letter
  at 44.1 kHz (see `spikes/02-synthesis-research-josh.md`). Phase 1
  ships with `josh-f1` as a single-voice default; multi-voice mapping
  (V2 of plan v2) is the natural Phase 1 follow-up.
- **Diarization (decided 2026-05-16, Spike B, partial):** the spike
  uses an in-house `cluster_speakers_by_pitch` in
  `spikes/02_synthesis.py` as a poor-man's diarization (pitch-based
  clustering, anonymous, in-clip only). Phase 1 should keep this as a
  CPU-only fallback but prefer pyannote/speaker-diarization-3.1 (or
  equivalent embedding-based method) when available, both for
  in-clip quality and for the cross-clip speaker-identity workflow
  proposed in `docs/speaker-workflow-plan.md`. The embedding spike
  ("Pre-adoption work" in that plan) is the gating item.

These were listed in `docs/spike-plan.md` and are recorded here as
Phase 0 closes.

## Contract changes implied by Phase 0 findings

The decisions above mean two contracts in this document are wrong as
written. Listed here for explicit revision in a Phase 1 PR (not
in-passing edits):

- **`VoiceEvent` → `WordEvent`.** The onset-driven `VoiceEvent`
  (`time_s` / `duration_s` / `pitch_hz` / `energy` / `voiced`) is
  unused. The actual contract between analyzer and synthesizer is
  word-level: `text: str`, `start_s: float`, `end_s: float`,
  `pitch_hz: float`, `speaker_id: str | None`. The `voiced` /
  `energy` fields don't translate; ASR already gates voiced regions
  by virtue of producing words only inside them.
- **`Synthesizer` becomes multi-bank-aware.** The current contract
  (`synthesize(events, sample_bank) -> np.ndarray`) takes a single
  bank. Multi-voice rendering (V2 of plan v2) needs
  `synthesize(events, bank_pool, speaker_to_bank) -> np.ndarray` or
  similar — the synthesizer picks the bank per event based on its
  `speaker_id`.

Both changes are PR-sized and should land in Phase 1, not retroactively
edited into the Phase 0 architecture text.
