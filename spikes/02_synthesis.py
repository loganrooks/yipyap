"""Spike B — onset / cadence / ASR-driven animalese synthesis.

Throwaway script. Three placement modes for the animalese letter samples:

1. **Onset-triggered** (default): VAD → onset detection → pyin pitch → one
   letter fired per onset.
2. **Fixed-cadence** (``--rate-hz``): a letter every ``1/rate_hz`` seconds
   inside voiced regions, ignoring onsets. ~12-13 Hz mirrors animalese.js's
   ``output_letter_secs = 0.075``.
3. **ASR-driven** (``--asr-input``): mlx-whisper transcribes the *original*
   clip (NOT the separated voice stem — separation removes too much for
   reliable ASR). Each word becomes its real spelling, rendered back-to-back
   at ``word_duration / num_letters`` per letter, pitched to the median pyin
   estimate over the word's time range on the cleaner voice stem. Inter-word
   silence is preserved exactly from the source's word timestamps. This is
   the spike-plan's documented transcription fallback.

See ``docs/spike-plan.md`` for the cadence / timbre / combined sub-tests.

Usage::

    # Cadence test (inline sine bank, ugly by design — judge rhythm only).
    python spikes/02_synthesis.py path/to/voice.wav

    # Timbre test (real animalese bank from a directory of .wav files).
    python spikes/02_synthesis.py path/to/voice.wav --samples-dir spikes/samples/

    # Combined verdict (real bank + background stem from Spike A).
    python spikes/02_synthesis.py path/to/voice.wav path/to/background.wav \\
        --samples-dir spikes/samples/

    # High-tessitura compensation — animalese is pitched up.
    python spikes/02_synthesis.py path/to/voice.wav --pitch-offset 12

    # Fixed cadence (animalese.js style).
    python spikes/02_synthesis.py path/to/voice.wav --samples-dir spikes/samples/ \\
        --rate-hz 13

    # ASR-driven (transcript -> per-word animalese).
    python spikes/02_synthesis.py voice.wav background.wav \\
        --samples-dir spikes/samples/ --pitch-offset 12 \\
        --asr-input spikes/inputs/clip.wav

Outputs land in ``spikes/output/spike-b/``:

- inline bank → ``spike-b-cadence.wav`` (+ ``spike-b-cadence-mixed.wav`` with bg)
- ``--samples-dir`` → ``spike-b-real.wav`` (+ ``spike-b-real-mixed.wav`` with bg)
- ``--asr-input`` → ``spike-b-asr.wav`` (+ ``spike-b-asr-mixed.wav`` with bg)
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from collections import Counter
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import torch
from silero_vad import get_speech_timestamps, load_silero_vad

SPIKE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SPIKE_DIR / "output" / "spike-b"

# Work at a single sample rate end-to-end. Silero expects 16 kHz; rendering at
# the same rate keeps the script dependency-free of resampling for output.
WORK_SR = 16_000

# Inline animalese bank: short pitched blips with ADSR-ish envelope. The base
# pitch is also the fallback base for loaded samples when pyin can't estimate
# their dominant pitch.
BANK_BASE_HZ = 270.0
BANK_SEED = 1729
N_BANK_SAMPLES = 8

# Per-onset placement smoothing. A short fade-in / fade-out at placement time
# eliminates clicks at sample boundaries. The cap below is just a defensive
# ceiling so a misconfigured user-supplied sample bank doesn't ring forever —
# real animalese-shaped samples are ~150ms, well under this limit, and the
# `time-to-next-onset` constraint usually dominates anyway. An earlier
# attempt at 90ms here introduced "bad radio" dropouts because onsets at
# 5–7/sec are ~150–200ms apart and the 90ms cap left 60–110ms of silence
# between every consecutive sample.
SAMPLE_PLACEMENT_MAX_S = 0.300
FADE_IN_S = 0.003
FADE_OUT_S = 0.020


def load_mono(path: Path, target_sr: int) -> np.ndarray:
    """Load ``path`` as float32 mono at ``target_sr``."""
    y, _ = librosa.load(str(path), sr=target_sr, mono=True)
    return y.astype(np.float32)


def voiced_regions(y: np.ndarray, sr: int) -> list[tuple[float, float]]:
    """Return ``[(start_s, end_s), ...]`` voiced regions via silero-vad."""
    if sr != 16_000:
        raise ValueError(f"silero-vad expects 16kHz, got {sr}")
    model = load_silero_vad()
    tensor = torch.from_numpy(y)
    stamps = get_speech_timestamps(
        tensor, model, sampling_rate=16_000, return_seconds=True
    )
    return [(float(s["start"]), float(s["end"])) for s in stamps]


def onsets_in_region(
    y: np.ndarray, sr: int, start_s: float, end_s: float
) -> list[float]:
    """Detect onsets inside ``[start_s, end_s]`` and return absolute times."""
    s_idx = max(0, int(start_s * sr))
    e_idx = min(y.size, int(end_s * sr))
    seg = y[s_idx:e_idx]
    if seg.size < 2048:
        return []
    times = librosa.onset.onset_detect(
        y=seg, sr=sr, units="time", backtrack=False, hop_length=512
    )
    return [float(t + start_s) for t in times]


def pitch_at(y: np.ndarray, sr: int, t_s: float, window_s: float = 0.08) -> float:
    """Estimate f0 (Hz) around time ``t_s``. Returns 0 if unvoiced or too short."""
    half = int(window_s * sr / 2)
    s_idx = max(0, int(t_s * sr) - half)
    e_idx = min(y.size, int(t_s * sr) + half)
    seg = y[s_idx:e_idx]
    if seg.size < 1024:
        return 0.0
    try:
        f0, _, _ = librosa.pyin(
            seg,
            fmin=float(librosa.note_to_hz("C2")),
            fmax=float(librosa.note_to_hz("C6")),
            sr=sr,
            frame_length=1024,
        )
    except Exception:
        return 0.0
    f0_valid = f0[~np.isnan(f0)]
    if f0_valid.size == 0:
        return 0.0
    return float(np.median(f0_valid))


def estimate_base_hz(y: np.ndarray, sr: int) -> float:
    """Estimate the dominant pitch of a whole sample. Returns 0 if undetectable."""
    if y.size < 1024:
        return 0.0
    try:
        f0, _, _ = librosa.pyin(
            y,
            fmin=float(librosa.note_to_hz("C2")),
            fmax=float(librosa.note_to_hz("C6")),
            sr=sr,
            frame_length=1024,
        )
    except Exception:
        return 0.0
    voiced = f0[~np.isnan(f0)]
    if voiced.size == 0:
        return 0.0
    return float(np.median(voiced))


def build_inline_bank(sr: int) -> list[tuple[np.ndarray, float]]:
    """Generate the inline pitched-blip bank as ``(sample, base_hz)`` pairs.

    Deterministic by seed. The base pitch is the bank's nominal centre
    (``BANK_BASE_HZ``); per-sample pitch wobble is small enough that we treat
    them as a single base for pitch-shift maths.
    """
    rng = np.random.default_rng(seed=BANK_SEED)
    bank: list[tuple[np.ndarray, float]] = []
    for _ in range(N_BANK_SAMPLES):
        f0 = float(rng.uniform(220.0, 360.0))
        dur_s = float(rng.uniform(0.07, 0.13))
        n = int(dur_s * sr)
        t = np.arange(n, dtype=np.float32) / sr
        wave = (
            0.7 * np.sin(2 * np.pi * f0 * t)
            + 0.2 * np.sin(2 * np.pi * 2 * f0 * t)
            + 0.1 * np.sin(2 * np.pi * 3 * f0 * t)
        ).astype(np.float32)
        env = np.ones(n, dtype=np.float32)
        atk = max(1, int(0.01 * sr))
        rel = max(1, int(0.04 * sr))
        env[:atk] = np.linspace(0.0, 1.0, atk, dtype=np.float32)
        env[-rel:] = np.linspace(1.0, 0.0, rel, dtype=np.float32)
        bank.append((wave * env, BANK_BASE_HZ))
    return bank


def load_samples_bank(samples_dir: Path, sr: int) -> list[tuple[np.ndarray, float]]:
    """Load every ``.wav`` in ``samples_dir`` as a ``(sample, base_hz)`` pair.

    Two clean-up passes applied to every sample:

    1. **Gentle low-pass** at ~4.5 kHz to mask 8-bit quantization hash. The
       animalese.js bank ships as PCM_U8 (256 levels, ~48 dB SNR) — fine in
       isolation but adds up as audible static when many overlap.
    2. **Outlier-correcting base pitch.** pyin sometimes locks onto an
       octave-error fundamental (the bundled letter 'X' detects at ~122 Hz
       while every other letter is ~250 Hz). We compute the median of
       confident estimates across the bank and clamp any sample whose
       estimate is >1.5× off the median back to that median — otherwise the
       affected letters chirp out at the wrong pitch / speed each time they
       get picked.
    """
    from scipy.signal import butter, sosfiltfilt

    wav_paths = sorted(p for p in samples_dir.glob("*.wav") if p.is_file())
    if not wav_paths:
        raise FileNotFoundError(
            f"--samples-dir {samples_dir} contains no .wav files."
        )

    # Smoothing filter — 2nd-order Butterworth at ~4.5 kHz removes the high
    # band where 8-bit quantization noise lives without dulling the syllable
    # character.
    cutoff = min(4500.0, sr * 0.45)
    sos = butter(2, cutoff, btype="low", fs=sr, output="sos")

    raw: list[tuple[Path, np.ndarray, float]] = []
    for p in wav_paths:
        s = load_mono(p, sr)
        if s.size == 0:
            print(f"[spike-b] WARN: skipping empty sample {p.name}", file=sys.stderr)
            continue
        s = sosfiltfilt(sos, s).astype(np.float32)
        base = estimate_base_hz(s, sr)
        raw.append((p, s, base))
    if not raw:
        raise FileNotFoundError(
            f"--samples-dir {samples_dir} had .wav files but all were empty."
        )

    # Outlier-correct against the median of confident estimates
    confident = [b for _, _, b in raw if b > 0]
    median_base = float(np.median(confident)) if confident else BANK_BASE_HZ
    bank: list[tuple[np.ndarray, float]] = []
    corrected = 0
    for p, s, base in raw:
        if base <= 0:
            corrected_base = median_base
            corrected += 1
        elif base / median_base > 1.5 or median_base / base > 1.5:
            corrected_base = median_base
            corrected += 1
        else:
            corrected_base = base
        bank.append((s, corrected_base))
        flag = " (outlier→median)" if corrected_base != base else ""
        print(
            f"[spike-b] loaded {p.name}: {s.size / sr:.3f}s, "
            f"base~{corrected_base:.1f}Hz{flag}"
        )
    print(f"[spike-b] bank median base: {median_base:.1f}Hz, outliers corrected: {corrected}")
    return bank


def apply_fades(
    s: np.ndarray, fade_in_n: int, fade_out_n: int
) -> np.ndarray:
    """Return a copy of ``s`` with linear fade-in / fade-out applied.

    Used at sample-placement time so per-onset truncation never produces a
    click at the cut boundary, regardless of where in the natural envelope
    the truncation lands.
    """
    if s.size == 0:
        return s
    out = s.copy()
    fi = min(fade_in_n, out.size // 2)
    fo = min(fade_out_n, out.size - fi)
    if fi > 0:
        out[:fi] *= np.linspace(0.0, 1.0, fi, dtype=np.float32)
    if fo > 0:
        out[-fo:] *= np.linspace(1.0, 0.0, fo, dtype=np.float32)
    return out


def pitch_shift_from_to(
    sample: np.ndarray, base_hz: float, target_hz: float, sr: int
) -> np.ndarray:
    """Sample-skip pitch shift (animalese.js-style linear resampling).

    ``ratio = target_hz / base_hz``. Plays back the sample at ``ratio`` speed,
    which raises pitch and shortens duration together — same trick the
    original animalese.js uses (``letter_library[start + floor(i * pitch)]``).

    Why not ``librosa.effects.pitch_shift``: that uses an STFT phase vocoder
    with a default 2048-sample (128 ms @ 16 kHz) window. Animalese-style
    letter samples are ~150 ms, so each shift has barely one analysis frame
    and the phase-vocoder smearing comes out audibly as static / fuzz.
    Sample-skip resampling is artifact-free in the time domain — exactly the
    "lo-fi but clean" character Animal Crossing has.
    """
    if base_hz <= 0 or target_hz <= 0 or sample.size == 0:
        return sample
    ratio = target_hz / base_hz
    if ratio == 1.0:
        return sample
    new_len = max(1, int(round(sample.size / ratio)))
    indices = np.linspace(0.0, float(sample.size - 1), new_len)
    return np.interp(indices, np.arange(sample.size, dtype=np.float32), sample).astype(np.float32)


def _transcribe_mlx_raw(
    audio_path: Path, model_repo: str, initial_prompt: str | None
) -> dict:
    """Single mlx-whisper call. Returns the raw result dict."""
    import mlx_whisper

    return mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=model_repo,
        word_timestamps=True,
        language="en",
        condition_on_previous_text=False,
        no_speech_threshold=0.3,
        initial_prompt=initial_prompt,
    )


def _transcribe_faster_raw(
    audio_path: Path, model_id: str, initial_prompt: str | None
) -> dict:
    """Single faster-whisper call. Adapts the segment/word iterator output
    to the same dict shape as mlx-whisper so the downstream parser is
    backend-agnostic.

    CUDA is picked automatically when available; otherwise CPU with int8
    quantization (CT2's standard low-RAM compute path).
    """
    import faster_whisper
    import torch

    if torch.cuda.is_available():
        device, compute_type = "cuda", "float16"
    else:
        device, compute_type = "cpu", "int8"

    model = faster_whisper.WhisperModel(
        model_id, device=device, compute_type=compute_type
    )
    segments_iter, _info = model.transcribe(
        str(audio_path),
        word_timestamps=True,
        language="en",
        condition_on_previous_text=False,
        no_speech_threshold=0.3,
        initial_prompt=initial_prompt,
    )

    segments_out: list[dict] = []
    for seg in segments_iter:
        seg_words = []
        for w in seg.words or []:
            seg_words.append(
                {"word": w.word, "start": float(w.start), "end": float(w.end)}
            )
        segments_out.append({
            "text": seg.text,
            "start": float(seg.start),
            "end": float(seg.end),
            "words": seg_words,
        })
    return {"segments": segments_out}


def transcribe_full(
    audio_path: Path,
    model_id: str,
    initial_prompt: str | None = None,
    backend: str = "mlx",
) -> tuple[list[dict], list[dict]]:
    """Transcribe ``audio_path``. Returns ``(words, segments)``.

    Each ``words`` entry is ``{text, letters, start, end, segment_idx}`` —
    ``text`` preserves the original casing/punctuation Whisper produced,
    ``letters`` is the A-Z-only render-pipeline form. Each ``segments``
    entry is ``{text, start, end}`` — Whisper's sentence-ish chunks (good
    for SRT-style readable display).

    ``initial_prompt`` is treated as decoder context preceding the audio:
    Whisper shifts its prior toward tokens in the prompt. Use it to fix
    chronic proper-noun mistakes (e.g. ``Piastri`` -> ``P history``).
    None disables prompting.

    ``backend`` dispatches to mlx-whisper (Apple Silicon, Metal GPU) or
    faster-whisper (portable; CUDA when present, CPU int8 fallback).
    Both return identical dict shapes so the parser below is shared.

    The caller should hand this the **original** clip (engines + commentary),
    NOT the MDX-separated voice stem: MDX's aggressive vocal-isolation
    silences too many sub-syllable transients for Whisper's internal VAD to
    cope with. Whisper handles broadcast noise natively.
    """
    def _run(prompt: str | None) -> dict:
        if backend == "mlx":
            return _transcribe_mlx_raw(audio_path, model_id, prompt)
        if backend == "faster":
            return _transcribe_faster_raw(audio_path, model_id, prompt)
        raise ValueError(
            f"Unknown ASR backend {backend!r}; expected 'mlx' or 'faster'."
        )

    def _renderable_words(res) -> int:
        # Count words whose token has any A-Z character. Punctuation-only
        # tokens like "!" don't count — they would be filtered out downstream
        # and produce an empty render.
        n = 0
        for seg in res["segments"]:
            for w in seg.get("words", []):
                if any("A" <= c <= "Z" for c in w["word"].upper()):
                    n += 1
        return n

    # Defensive fallback threshold: F1 commentary runs ~2-4 words/sec
    # sustained, so a 30s clip with fewer than 10 renderable words is
    # almost certainly a prompt-induced failure. Two failure modes seen:
    #   - whisper-base + long F1 prompt on a Monza highlight: 0 words,
    #     just `!` (prompt-induced hallucination of empty output).
    #   - whisper-small + long F1 prompt on the same clip: 6 words, just
    #     a few driver names echoed back from the prompt (prompt hijacked
    #     the decoder).
    # Both retry cleanly without the prompt.
    PROMPT_FALLBACK_THRESHOLD = 10

    result = _run(initial_prompt)
    if (
        initial_prompt
        and _renderable_words(result) < PROMPT_FALLBACK_THRESHOLD
    ):
        print(
            f"[spike-b] WARN: initial_prompt produced "
            f"{_renderable_words(result)} renderable words for "
            f"{audio_path.name} (threshold {PROMPT_FALLBACK_THRESHOLD}). "
            f"Retrying without prompt — proper-noun mistakes may remain.",
            file=sys.stderr,
        )
        result = _run(None)
    words: list[dict] = []
    segments: list[dict] = []
    for seg_idx, seg in enumerate(result["segments"]):
        segments.append({
            "text": seg["text"].strip(),
            "start": float(seg["start"]),
            "end": float(seg["end"]),
        })
        for w in seg.get("words", []):
            text = w["word"].strip()
            letters = "".join(c for c in text.upper() if "A" <= c <= "Z")
            if not letters:
                continue  # pure punctuation/digit token — not renderable
            words.append({
                "text": text,
                "letters": letters,
                "start": float(w["start"]),
                "end": float(w["end"]),
                "segment_idx": seg_idx,
            })
    return words, segments


def format_srt_timestamp(seconds: float) -> str:
    """Format ``seconds`` as ``HH:MM:SS,mmm`` for SRT subtitle files."""
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def write_transcript_sidecars(
    wav_path: Path,
    words: list[dict],
    segments: list[dict],
    speaker_labels: list[int] | None,
) -> tuple[Path, Path]:
    """Persist transcript next to ``wav_path`` as ``.json`` and ``.srt``.

    JSON keeps everything: per-word + per-segment timing, original text,
    A-Z render form, segment index, optional speaker label. Ready input
    for a future Animal-Crossing-style blurb renderer.

    SRT is one entry per Whisper segment (sentence-ish chunks), prefixed
    with ``[Speaker N]`` if diarization labels are present. Drop-in for
    ``ffmpeg -vf subtitles=...`` overlay on the source video.
    """
    if speaker_labels is not None and len(speaker_labels) == len(words):
        for i, lab in enumerate(speaker_labels):
            words[i]["speaker"] = int(lab)

    # Majority-vote a speaker label per segment from the words it contains.
    segment_speakers: dict[int, list[int]] = {}
    for w in words:
        if "speaker" not in w:
            continue
        segment_speakers.setdefault(w["segment_idx"], []).append(w["speaker"])

    json_path = wav_path.with_suffix(".json")
    json_path.write_text(json.dumps(
        {"words": words, "segments": segments}, indent=2, ensure_ascii=False,
    ))

    srt_path = wav_path.with_suffix(".srt")
    srt_lines: list[str] = []
    for i, seg in enumerate(segments):
        speakers = segment_speakers.get(i, [])
        prefix = ""
        if speakers:
            majority = Counter(speakers).most_common(1)[0][0]
            prefix = f"[Speaker {majority}] "
        srt_lines.append(f"{i + 1}")
        srt_lines.append(
            f"{format_srt_timestamp(seg['start'])} --> "
            f"{format_srt_timestamp(seg['end'])}"
        )
        srt_lines.append(f"{prefix}{seg['text']}")
        srt_lines.append("")
    srt_path.write_text("\n".join(srt_lines))
    return json_path, srt_path


def pitch_over_range(
    y: np.ndarray, sr: int, t_start_s: float, t_end_s: float
) -> float:
    """Median pyin pitch across ``[t_start_s, t_end_s]``. 0 if unvoiced/too short."""
    s_idx = max(0, int(t_start_s * sr))
    e_idx = min(y.size, int(t_end_s * sr))
    seg = y[s_idx:e_idx]
    if seg.size < 1024:
        return 0.0
    try:
        f0, _, _ = librosa.pyin(
            seg,
            fmin=float(librosa.note_to_hz("C2")),
            fmax=float(librosa.note_to_hz("C6")),
            sr=sr,
            frame_length=1024,
        )
    except Exception:
        return 0.0
    valid = f0[~np.isnan(f0)]
    return float(np.median(valid)) if valid.size else 0.0


# ASR-mode per-letter cadence clamp. animalese.js uses a fixed 75 ms, but for
# spoken text the per-letter duration tracks the word's actual duration —
# shorter words use faster letters. We clamp to keep the rate in a
# perceptually-natural band even for very-fast or very-slow words.
LETTER_MIN_S = 0.045  # ~22 letters/sec ceiling
LETTER_MAX_S = 0.150  # ~6.7 letters/sec floor

# Backend selection registries. Logical sizes are translated to
# backend-specific model identifiers at runtime; users can also pass a full
# repo identifier (anything containing '/') as a literal pass-through.
MLX_SIZE_TO_REPO = {
    "tiny": "mlx-community/whisper-tiny.en-mlx",
    "base": "mlx-community/whisper-base.en-mlx",
    "small": "mlx-community/whisper-small.en-mlx",
    "medium": "mlx-community/whisper-medium.en-mlx",
    "large": "mlx-community/whisper-large-v3-mlx",
    "turbo": "mlx-community/whisper-large-v3-turbo",
}
FASTER_SIZE_TO_REPO = {
    "tiny": "tiny.en",
    "base": "base.en",
    "small": "small.en",
    "medium": "medium.en",
    "large": "large-v3",
    "turbo": "large-v3-turbo",
}

# Per-backend defaults when the user doesn't pass --asr-model. Calibrated
# for the typical host profile: small on Apple Silicon (base.en
# undertranscribes proper nouns), turbo on Linux+CUDA with 8GB+ VRAM.
DEFAULT_SIZE_BY_BACKEND = {"mlx": "small", "faster": "turbo"}


def select_asr_backend() -> str:
    """Detect best ASR backend for the current host.

    'mlx' on Apple Silicon when mlx-whisper imports; 'faster' elsewhere
    when faster-whisper imports. Raises if neither is installed.
    """
    is_apple_silicon = (
        sys.platform == "darwin" and platform.machine() == "arm64"
    )
    if is_apple_silicon:
        try:
            import mlx_whisper  # noqa: F401

            return "mlx"
        except ImportError:
            pass
    try:
        import faster_whisper  # noqa: F401

        return "faster"
    except ImportError as exc:
        raise RuntimeError(
            "No ASR backend available. Install mlx-whisper (Apple Silicon) "
            "or faster-whisper (any platform). See spikes/requirements.txt."
        ) from exc


def resolve_asr_model(model_arg: str | None, backend: str) -> str:
    """Translate a logical size to a backend-specific model id.

    None -> backend default. A token containing '/' is treated as a full
    repo identifier and passed through unchanged. A bare logical size
    (tiny/base/small/medium/large/turbo) is looked up in the appropriate
    registry. Anything else (e.g. ``large-v3``, ``small.en``) is also
    passed through — faster-whisper accepts those directly.
    """
    if model_arg is None:
        size = DEFAULT_SIZE_BY_BACKEND[backend]
        return (MLX_SIZE_TO_REPO if backend == "mlx" else FASTER_SIZE_TO_REPO)[size]
    if "/" in model_arg:
        return model_arg
    size = model_arg.lower()
    registry = MLX_SIZE_TO_REPO if backend == "mlx" else FASTER_SIZE_TO_REPO
    return registry.get(size, model_arg)


def select_torch_device():
    """Best torch device for pyannote / general inference.

    Order: CUDA > MPS > CPU. Returns a ``torch.device``.
    """
    import torch

    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


# F1-broadcast vocabulary biasing for Whisper. Without this, base.en
# routinely transcribes "Piastri" as "P history", "Verstappen" as
# "Verschappen", "Tsunoda" as "Sanoda", etc. The string is fed to
# mlx-whisper as `initial_prompt`, treated as decoder context preceding
# the audio — Whisper's prior over its next-token distribution shifts
# toward tokens in the prompt. Whisper caps the prompt at ~224 tokens;
# this one is comfortably under that.
DEFAULT_F1_ASR_PROMPT = (
    "Formula 1 race commentary featuring drivers Max Verstappen, "
    "Sergio Perez, Lewis Hamilton, George Russell, Charles Leclerc, "
    "Carlos Sainz, Lando Norris, Oscar Piastri, Fernando Alonso, "
    "Lance Stroll, Pierre Gasly, Esteban Ocon, Yuki Tsunoda, "
    "Daniel Ricciardo, Liam Lawson, Valtteri Bottas, Zhou Guanyu, "
    "Kevin Magnussen, Nico Hulkenberg, Alex Albon, Logan Sargeant, "
    "Andrea Kimi Antonelli, Oliver Bearman, Gabriel Bortoleto. "
    "Teams: Red Bull, Mercedes, Ferrari, McLaren, Aston Martin, "
    "Alpine, RB, Williams, Sauber, Haas."
)


def render_word(
    word_text: str,
    word_start_s: float,
    word_end_s: float,
    pitch_hz: float,
    bank: list[tuple[np.ndarray, float]],
    sr: int,
    pitch_offset_factor: float,
    fade_n: int,
) -> tuple[int, np.ndarray]:
    """Render one word as back-to-back animalese letters at a single pitch.

    Letters are **overlap-added** by ``fade_n`` samples so the fade-out of
    each letter crossfades with the fade-in of the next. Sequential (non-
    overlapping) concatenation produced an amplitude dip between every
    letter at ~15+ letters/sec, which read as static / fuzz; the crossfade
    eliminates that dip while preserving each letter's individual shape.

    Returns ``(start_sample_index, rendered_audio)``.
    """
    if not word_text or pitch_hz <= 0:
        return int(word_start_s * sr), np.zeros(0, dtype=np.float32)
    duration_s = max(0.040, word_end_s - word_start_s)
    per_letter_s = float(np.clip(duration_s / len(word_text), LETTER_MIN_S, LETTER_MAX_S))
    out_n = int(per_letter_s * sr)
    target_hz = pitch_hz * pitch_offset_factor
    local_fade = max(1, min(fade_n, out_n // 3))

    chunks: list[np.ndarray] = []
    for ch in word_text:
        idx = ord(ch) - ord("A")
        if not (0 <= idx < len(bank)):
            continue
        sample, base_hz = bank[idx]
        shifted = pitch_shift_from_to(sample, base_hz, target_hz, sr)
        if shifted.size >= out_n:
            chunk = shifted[:out_n].copy()
        else:
            chunk = np.zeros(out_n, dtype=np.float32)
            chunk[: shifted.size] = shifted
        # Equal-power-ish linear fade. With overlap-add at local_fade, the
        # two halves sum to ~constant amplitude across the crossfade region.
        chunk[:local_fade] *= np.linspace(0.0, 1.0, local_fade, dtype=np.float32)
        chunk[-local_fade:] *= np.linspace(1.0, 0.0, local_fade, dtype=np.float32)
        chunks.append(chunk)
    if not chunks:
        return int(word_start_s * sr), np.zeros(0, dtype=np.float32)

    # Overlap-add: letter i starts at i * (out_n - local_fade)
    step = out_n - local_fade
    total_n = (len(chunks) - 1) * step + out_n
    rendered = np.zeros(total_n, dtype=np.float32)
    for i, chunk in enumerate(chunks):
        pos = i * step
        rendered[pos : pos + chunk.size] += chunk
    return int(word_start_s * sr), rendered


def cluster_speakers_by_pitch(
    word_pitches: list[float], n_speakers: int = 2, max_iter: int = 30
) -> tuple[list[int], list[float]]:
    """1-D k-means cluster word pitches into ``n_speakers`` groups.

    Designed for the documented "always two speakers" case: F1 broadcast
    booths almost always run with two co-commentators alternating, so a
    purpose-built k=2 clustering is way cheaper than full diarization (no
    pyannote dependency, no embeddings, no model). Carries last-assigned
    label through unvoiced words so a fallback word inherits the speaker
    label of the previous word it was sandwiched against.

    Returns ``(labels_per_word, cluster_centers_hz)``.
    """
    valid = [p for p in word_pitches if p > 0]
    if len(valid) < n_speakers or n_speakers < 2:
        return [0] * len(word_pitches), [float(np.median(valid)) if valid else 0.0]

    pmin, pmax = float(min(valid)), float(max(valid))
    if pmax <= pmin:
        return [0] * len(word_pitches), [pmin]
    centers = [pmin + (pmax - pmin) * i / (n_speakers - 1) for i in range(n_speakers)]
    assignments_for_valid: list[int] = [0] * len(word_pitches)

    for _ in range(max_iter):
        new_assignments: list[int] = []
        for p in word_pitches:
            if p <= 0:
                new_assignments.append(-1)
                continue
            distances = [abs(p - c) for c in centers]
            new_assignments.append(int(np.argmin(distances)))
        new_centers: list[float] = []
        for k in range(n_speakers):
            members = [word_pitches[i] for i, a in enumerate(new_assignments) if a == k]
            new_centers.append(float(np.mean(members)) if members else centers[k])
        converged = all(abs(c1 - c2) < 0.1 for c1, c2 in zip(centers, new_centers))
        centers = new_centers
        assignments_for_valid = new_assignments
        if converged:
            break

    # Fill the -1 (unpitched) words by carrying the most recent confident label.
    labels: list[int] = []
    last = 0
    for a in assignments_for_valid:
        if a >= 0:
            last = a
        labels.append(last)
    # Always emit cluster 0 as the LOWER pitch (more interpretable downstream).
    order = sorted(range(n_speakers), key=lambda k: centers[k])
    remap = {old: new for new, old in enumerate(order)}
    labels = [remap[l] for l in labels]
    centers = sorted(centers)
    return labels, centers


def diarize_speakers(
    audio_path: Path,
    hf_token: str,
    min_speakers: int = 1,
    max_speakers: int = 4,
) -> list[tuple[float, float, int]]:
    """Run pyannote-audio speaker diarization on ``audio_path``.

    Returns ``[(start_s, end_s, speaker_idx), ...]`` sorted by start time.
    Speaker indices are remapped to 0..N-1 in order of first appearance.

    Why pyannote instead of pitch clustering: voice timbre (formant /
    vocal-tract resonances) stays stable across a speaker's prosodic range,
    but pitch does not — F1 commentary regularly jumps an octave when a
    driver wins. pyannote embeds the timbre directly and clusters on that,
    so Lando-cheering and Lando-talking land in the same speaker. The
    ``min_speakers=1, max_speakers=4`` default mirrors F1-broadcast reality:
    usually 2 (lap-by-lap + colour), occasionally 1 (solo lead) or 3-4
    (booth + driver radio + interview).
    """
    from pyannote.audio import Pipeline

    # pyannote.audio v4 renamed `use_auth_token` -> `token`.
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token=hf_token,
    )
    device = select_torch_device()
    if device.type != "cpu":
        pipeline.to(device)

    diarization = pipeline(
        str(audio_path),
        min_speakers=min_speakers,
        max_speakers=max_speakers,
    )

    # pyannote.audio v4 returns DiarizeOutput with `.speaker_diarization`
    # (may contain overlapping turns) and `.exclusive_speaker_diarization`
    # (single-speaker-per-frame, suitable for downstream transcription). We
    # use the exclusive variant for word labeling — overlapping turns would
    # ambiguate the word→speaker assignment.
    annotation = diarization.exclusive_speaker_diarization

    segments: list[tuple[float, float, int]] = []
    speaker_order: dict[str, int] = {}
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        if speaker not in speaker_order:
            speaker_order[speaker] = len(speaker_order)
        segments.append(
            (float(turn.start), float(turn.end), speaker_order[speaker])
        )
    segments.sort(key=lambda x: x[0])
    return segments


def assign_words_to_speakers(
    words: list[dict],
    segments: list[tuple[float, float, int]],
) -> list[int]:
    """Match each Whisper word to a pyannote speaker label.

    Strategy: the segment whose interval contains the word's midpoint wins.
    If no segment contains the midpoint, the nearest segment by edge
    distance wins (handles word/segment boundary misalignment, which is
    routine when ASR and diarization aren't jointly trained).
    """
    if not segments:
        return [0] * len(words)
    labels: list[int] = []
    for w in words:
        mid = (w["start"] + w["end"]) / 2.0
        hit = next(
            ((s, e, k) for s, e, k in segments if s <= mid <= e), None
        )
        if hit is not None:
            labels.append(hit[2])
            continue
        nearest = min(
            segments, key=lambda seg: min(abs(mid - seg[0]), abs(mid - seg[1]))
        )
        labels.append(nearest[2])
    return labels


def synthesize(
    voice_path: Path,
    background_path: Path | None,
    samples_dir: Path | None,
    pitch_offset_semitones: int,
    rate_hz: float,
    asr_input: Path | None,
    asr_model: str,
    n_speakers: int,
    speaker_spread_semitones: float,
    diarize: bool = False,
    min_speakers: int = 1,
    max_speakers: int = 4,
    asr_prompt: str | None = None,
    asr_backend: str = "mlx",
) -> dict[str, Path]:
    """Render the spike output(s). Filenames depend on which mode was used.

    Placement mode (checked in order):
    - ``asr_input`` set: ASR-driven (whisper transcript + per-word render).
    - ``rate_hz > 0``: fixed-cadence (animalese.js-style continuous letters).
    - else: onset-triggered (default).
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    y = load_mono(voice_path, WORK_SR)
    duration_s = y.size / WORK_SR
    print(f"[spike-b] voice {voice_path.name}: {duration_s:.2f}s @ {WORK_SR}Hz")

    if samples_dir is not None:
        print(f"[spike-b] bank: real (--samples-dir {samples_dir})")
        bank = load_samples_bank(samples_dir, WORK_SR)
        bank_kind = "real"
    else:
        print("[spike-b] bank: inline sine (cadence test)")
        bank = build_inline_bank(WORK_SR)
        bank_kind = "cadence"
    print(f"[spike-b] bank size: {len(bank)} samples")
    if pitch_offset_semitones:
        print(f"[spike-b] pitch offset: {pitch_offset_semitones:+d} semitones")

    out = np.zeros_like(y, dtype=np.float32)
    pitch_offset_factor = 2.0 ** (pitch_offset_semitones / 12.0)
    fade_in_n = max(1, int(FADE_IN_S * WORK_SR))
    fade_out_n = max(1, int(FADE_OUT_S * WORK_SR))

    # ---- ASR-driven branch (transcript -> per-word animalese) -------------
    if asr_input is not None:
        bank_kind = "asr"
        if samples_dir is None:
            raise RuntimeError(
                "--asr-input requires --samples-dir (the bank must have A-Z "
                "letter samples; the inline sine bank is rhythm-only)."
            )
        if len(bank) < 26:
            print(
                f"[spike-b] WARN: bank has only {len(bank)} samples but ASR "
                f"mode expects A-Z (26). Letters beyond the bank size will be "
                f"skipped.",
                file=sys.stderr,
            )
        print(f"[spike-b] ASR input: {asr_input}")
        print(f"[spike-b] ASR backend: {asr_backend}")
        print(f"[spike-b] ASR model: {asr_model}")
        if asr_prompt:
            print(
                f"[spike-b] ASR initial prompt: "
                f"{asr_prompt[:70]}{'...' if len(asr_prompt) > 70 else ''}"
            )
        else:
            print("[spike-b] ASR initial prompt: (none)")
        words, transcript_segments = transcribe_full(
            asr_input, asr_model, asr_prompt, asr_backend
        )
        print(
            f"[spike-b] ASR: {len(words)} words, "
            f"{len(transcript_segments)} segments"
        )
        if not words:
            raise RuntimeError(
                f"mlx-whisper returned 0 words for {asr_input}. Did you pass "
                f"the original clip, not an over-aggressively separated stem?"
            )

        # First pass: per-word pitch estimate (median pyin over the word's span)
        per_word_pitches: list[float] = []
        for w in words:
            per_word_pitches.append(
                pitch_over_range(y, WORK_SR, w["start"], w["end"])
            )

        # Label each word with a speaker. Two strategies:
        #   --diarize: pyannote-audio (embedding-based, handles within-speaker
        #              pitch range — Lando calm vs. Lando cheering stay
        #              together because timbre is stable across prosody).
        #   else: 1-D k-means on per-word pyin pitch (cheap, but legitimately
        #              splits one excited speaker into "two speakers" because
        #              their pitch range is huge).
        if diarize:
            # Accept either env-var or huggingface-cli-login cached token.
            # huggingface_hub.get_token() returns the cached token if present,
            # else None.
            from huggingface_hub import get_token as _hf_get_token

            hf_token = os.environ.get("HF_TOKEN") or _hf_get_token()
            if not hf_token:
                raise RuntimeError(
                    "--diarize needs a HuggingFace token. Two ways to set one up:\n"
                    "  (a) Run `huggingface-cli login` and paste a read token, OR\n"
                    "  (b) `export HF_TOKEN=<your-read-token>` in this shell.\n"
                    "Get a read token at https://huggingface.co/settings/tokens "
                    "and accept the model conditions at "
                    "https://hf.co/pyannote/speaker-diarization-3.1 first."
                )
            print(
                f"[spike-b] diarizing (min={min_speakers}, max={max_speakers} "
                f"speakers, pyannote/speaker-diarization-3.1)..."
            )
            segments = diarize_speakers(
                asr_input, hf_token, min_speakers, max_speakers
            )
            detected_speakers = len({k for _, _, k in segments}) if segments else 1
            print(
                f"[spike-b] diarization: {len(segments)} segments, "
                f"{detected_speakers} speakers detected"
            )
            speaker_labels = assign_words_to_speakers(words, segments)
            # Per-speaker reference pitch = median of confident word pitches
            # for that speaker. Used only for the diagnostic print.
            speaker_centers = []
            for k in range(detected_speakers):
                ps = [
                    per_word_pitches[i]
                    for i, lab in enumerate(speaker_labels)
                    if lab == k and per_word_pitches[i] > 0
                ]
                speaker_centers.append(float(np.median(ps)) if ps else 0.0)
            n_speakers_effective = detected_speakers
        else:
            # Cluster words into speakers (1-D k-means on pitch); n_speakers == 1
            # disables clustering. Per-speaker pitch-offset spread spreads the
            # output voices apart so the listener can hear them as distinct.
            speaker_labels, speaker_centers = cluster_speakers_by_pitch(
                per_word_pitches, n_speakers=n_speakers
            )
            n_speakers_effective = n_speakers

        if n_speakers_effective > 1:
            centers_str = ", ".join(f"{c:.0f}Hz" for c in speaker_centers)
            print(
                f"[spike-b] speakers ({n_speakers_effective}, "
                f"{'diarized' if diarize else 'pitch-clustered'}): {centers_str}"
            )
            print(
                f"[spike-b] speaker spread: ±{speaker_spread_semitones / 2:.1f} "
                f"semitones around base offset"
            )
        # Per-speaker offset distributed symmetrically around the base offset.
        # 2 speakers, spread=12 → speaker0 at base - 6, speaker1 at base + 6.
        if n_speakers_effective > 1 and speaker_spread_semitones != 0:
            step = speaker_spread_semitones / (n_speakers_effective - 1)
            per_speaker_extra = [
                -speaker_spread_semitones / 2 + k * step
                for k in range(n_speakers_effective)
            ]
        else:
            per_speaker_extra = [0.0] * max(n_speakers_effective, 1)

        placed_words = 0
        fallback_pitches = 0
        last_word_pitch = 0.0
        total_letters = 0
        per_speaker_count = [0] * max(n_speakers_effective, 1)
        for i, w in enumerate(words):
            w_pitch = per_word_pitches[i]
            if w_pitch <= 0:
                if last_word_pitch <= 0:
                    continue
                w_pitch = last_word_pitch
                fallback_pitches += 1
            else:
                last_word_pitch = w_pitch
            speaker = speaker_labels[i]
            word_offset_semitones = pitch_offset_semitones + per_speaker_extra[speaker]
            word_offset_factor = 2.0 ** (word_offset_semitones / 12.0)
            start_idx, rendered = render_word(
                w["letters"], w["start"], w["end"], w_pitch, bank, WORK_SR,
                word_offset_factor, fade_out_n,
            )
            if rendered.size == 0:
                continue
            end_idx = min(out.size, start_idx + rendered.size)
            out[start_idx:end_idx] += rendered[: end_idx - start_idx]
            placed_words += 1
            total_letters += len(w["letters"])
            per_speaker_count[speaker] += 1
        if n_speakers_effective > 1:
            for k, n in enumerate(per_speaker_count):
                print(
                    f"[spike-b] speaker {k}: {n} words, "
                    f"~{speaker_centers[k]:.0f}Hz src, "
                    f"offset {pitch_offset_semitones + per_speaker_extra[k]:+.1f} st"
                )
        print(
            f"[spike-b] rendered {placed_words} words ({total_letters} letters) "
            f"with {fallback_pitches} pitch fallbacks"
        )
        peak = float(np.max(np.abs(out))) if out.size else 0.0
        if peak > 0:
            out = (out / peak * 0.9).astype(np.float32)

        direct_path = OUTPUT_DIR / f"spike-b-{bank_kind}.wav"
        sf.write(direct_path, out, WORK_SR)
        print(f"[spike-b] wrote {direct_path}")
        outputs: dict[str, Path] = {"direct": direct_path}
        json_path, srt_path = write_transcript_sidecars(
            direct_path, words, transcript_segments, speaker_labels
        )
        print(f"[spike-b] wrote {json_path}")
        print(f"[spike-b] wrote {srt_path}")
        outputs["json"] = json_path
        outputs["srt"] = srt_path
        if background_path is not None:
            bg = load_mono(background_path, WORK_SR)
            n = min(out.size, bg.size)
            mixed = (out[:n] * 0.9 + bg[:n] * 0.9).astype(np.float32)
            peak_mix = float(np.max(np.abs(mixed)))
            if peak_mix > 1.0:
                mixed = (mixed / peak_mix).astype(np.float32)
            mixed_path = OUTPUT_DIR / f"spike-b-{bank_kind}-mixed.wav"
            sf.write(mixed_path, mixed, WORK_SR)
            print(f"[spike-b] wrote {mixed_path}")
            outputs["mixed"] = mixed_path
        return outputs
    # ---- End ASR branch ----------------------------------------------------

    regions = voiced_regions(y, WORK_SR)
    print(f"[spike-b] voiced regions: {len(regions)}")

    if rate_hz > 0:
        interval = 1.0 / float(rate_hz)
        placement_times: list[float] = []
        for start_s, end_s in regions:
            t = start_s
            while t < end_s:
                placement_times.append(t)
                t += interval
        print(
            f"[spike-b] fixed-cadence placement: {len(placement_times)} events "
            f"@ {rate_hz:.1f} Hz (every {interval*1000:.0f} ms)"
        )
    else:
        placement_times = []
        for start_s, end_s in regions:
            placement_times.extend(onsets_in_region(y, WORK_SR, start_s, end_s))
        placement_times.sort()
        print(f"[spike-b] onset-triggered placement: {len(placement_times)} events")

    rng = np.random.default_rng(seed=42)
    out = np.zeros_like(y, dtype=np.float32)
    pitch_offset_factor = 2.0 ** (pitch_offset_semitones / 12.0)

    fade_in_n = max(1, int(FADE_IN_S * WORK_SR))
    fade_out_n = max(1, int(FADE_OUT_S * WORK_SR))
    max_placement_n = int(SAMPLE_PLACEMENT_MAX_S * WORK_SR)

    placed = 0
    fallback_pitches = 0
    last_pitch_hz = 0.0
    for i, t_on in enumerate(placement_times):
        t_next = placement_times[i + 1] if i + 1 < len(placement_times) else duration_s
        # Allow each placement to bleed slightly past its successor so the
        # fade-out and the next fade-in produce a smooth equal-power crossfade
        # instead of butting against each other with no overlap.
        max_dur = max(t_next - t_on, 0.03) + FADE_OUT_S
        pitch_hz = pitch_at(y, WORK_SR, t_on)
        if pitch_hz <= 0:
            if last_pitch_hz <= 0:
                continue
            pitch_hz = last_pitch_hz
            fallback_pitches += 1
        else:
            last_pitch_hz = pitch_hz
        target_hz = pitch_hz * pitch_offset_factor
        sample, base_hz = bank[rng.integers(0, len(bank))]
        sample = pitch_shift_from_to(sample, base_hz, target_hz, WORK_SR)
        n_cap = min(max_placement_n, int(max_dur * WORK_SR), sample.size)
        if n_cap <= 0:
            continue
        placed_sample = apply_fades(sample[:n_cap], fade_in_n, fade_out_n)
        s_idx = int(t_on * WORK_SR)
        e_idx = min(out.size, s_idx + placed_sample.size)
        out[s_idx:e_idx] += placed_sample[: e_idx - s_idx]
        placed += 1

    print(
        f"[spike-b] placed {placed} samples "
        f"(skipped {len(placement_times) - placed} unvoiced/invalid, "
        f"used last-pitch fallback on {fallback_pitches})"
    )

    peak = float(np.max(np.abs(out))) if out.size else 0.0
    if peak > 0:
        out = (out / peak * 0.9).astype(np.float32)

    direct_path = OUTPUT_DIR / f"spike-b-{bank_kind}.wav"
    sf.write(direct_path, out, WORK_SR)
    print(f"[spike-b] wrote {direct_path}")

    outputs: dict[str, Path] = {"direct": direct_path}

    if background_path is not None:
        bg = load_mono(background_path, WORK_SR)
        n = min(out.size, bg.size)
        mixed = (out[:n] * 0.9 + bg[:n] * 0.9).astype(np.float32)
        peak_mix = float(np.max(np.abs(mixed)))
        if peak_mix > 1.0:
            mixed = (mixed / peak_mix).astype(np.float32)
        mixed_path = OUTPUT_DIR / f"spike-b-{bank_kind}-mixed.wav"
        sf.write(mixed_path, mixed, WORK_SR)
        print(f"[spike-b] wrote {mixed_path}")
        outputs["mixed"] = mixed_path

    return outputs


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Spike B — onset-aligned animalese on a voice stem."
    )
    parser.add_argument("voice_stem", type=Path, help="Path to isolated voice stem.")
    parser.add_argument(
        "background_stem",
        type=Path,
        nargs="?",
        default=None,
        help="Optional background stem to mix the animalese onto.",
    )
    parser.add_argument(
        "--samples-dir",
        type=Path,
        default=None,
        help="Directory of .wav samples for the real-bank timbre test. "
        "Omitted = inline sine bank (cadence test).",
    )
    parser.add_argument(
        "--pitch-offset",
        type=int,
        default=0,
        help="Semitones to shift the target pitch up/down before sample "
        "pitch-shifting. Use +12 for high-tessitura animalese banks.",
    )
    parser.add_argument(
        "--rate-hz",
        type=float,
        default=0.0,
        help=(
            "If > 0, place samples at this fixed cadence inside voiced "
            "regions instead of at detected onsets. ~12-13 Hz mirrors "
            "animalese.js's letter cadence (output_letter_secs = 0.075). "
            "0 (default) keeps onset-triggered placement."
        ),
    )
    parser.add_argument(
        "--asr-input",
        type=Path,
        default=None,
        help=(
            "If set, transcribe THIS audio file with mlx-whisper and render "
            "per-word animalese from the resulting word timestamps + "
            "spellings. Typically the ORIGINAL clip — MDX-separated voice "
            "stems are too aggressively cleaned for reliable ASR. Pitch is "
            "still tracked on the voice_stem positional arg. Requires "
            "--samples-dir."
        ),
    )
    parser.add_argument(
        "--asr-backend",
        type=str,
        default="auto",
        choices=("auto", "mlx", "faster"),
        help=(
            "Which Whisper backend to use. 'auto' picks mlx-whisper on "
            "Apple Silicon and faster-whisper everywhere else. Force "
            "'faster' on Apple Silicon if you want to test the CT2 path."
        ),
    )
    parser.add_argument(
        "--asr-model",
        type=str,
        default=None,
        help=(
            "Whisper model identifier. Accepts a logical size (tiny / "
            "base / small / medium / large / turbo) that's translated to "
            "the active backend's model id, OR a full repo identifier "
            "(contains '/' for HuggingFace) passed through unchanged. "
            "Default depends on backend: 'small' for mlx, 'turbo' for "
            "faster-whisper (8 GB+ VRAM machines)."
        ),
    )
    parser.add_argument(
        "--speakers",
        type=int,
        default=1,
        help=(
            "ASR-mode only. If >1, cluster words by pyin pitch into N "
            "speakers (1-D k-means) and apply distinct pitch offsets per "
            "cluster so the speakers sound audibly different. Default 1 "
            "(single voice)."
        ),
    )
    parser.add_argument(
        "--speaker-spread",
        type=float,
        default=12.0,
        help=(
            "Semitones of spread distributed symmetrically around --pitch-"
            "offset across the N speaker clusters. With --speakers 2 and "
            "--speaker-spread 12, speaker 0 (lower-pitch source) is "
            "rendered at pitch-offset - 6 and speaker 1 at pitch-offset + 6."
        ),
    )
    parser.add_argument(
        "--diarize",
        action="store_true",
        help=(
            "Use pyannote-audio for speaker labels instead of pitch "
            "clustering. Requires HF_TOKEN env var and acceptance of "
            "https://hf.co/pyannote/speaker-diarization-3.1 terms. The "
            "number of speakers is auto-detected within "
            "[--min-speakers, --max-speakers], overriding --speakers."
        ),
    )
    parser.add_argument(
        "--min-speakers",
        type=int,
        default=1,
        help=(
            "Lower bound on auto-detected speaker count when --diarize is "
            "set. F1 clips occasionally have only one voice (solo "
            "commentator), so default is 1."
        ),
    )
    parser.add_argument(
        "--max-speakers",
        type=int,
        default=4,
        help=(
            "Upper bound on auto-detected speaker count when --diarize is "
            "set. F1 clips can have a booth pair plus driver radio plus "
            "interview cut, so default is 4."
        ),
    )
    parser.add_argument(
        "--asr-prompt",
        type=str,
        default=None,
        help=(
            "Whisper initial_prompt — biases the decoder toward specific "
            "vocabulary. Default: a bundled F1 driver/team vocabulary that "
            "fixes chronic mistakes like 'P history' -> 'Piastri'. Pass "
            "--asr-prompt '' to disable prompting entirely, or supply your "
            "own short context string (capped at ~224 tokens by Whisper)."
        ),
    )
    args = parser.parse_args(argv)

    if not args.voice_stem.exists():
        print(f"ERROR: voice stem not found: {args.voice_stem}", file=sys.stderr)
        return 2
    if args.background_stem is not None and not args.background_stem.exists():
        print(f"ERROR: background stem not found: {args.background_stem}", file=sys.stderr)
        return 2

    if args.samples_dir is not None:
        if not args.samples_dir.exists():
            print(
                f"ERROR: --samples-dir not found: {args.samples_dir}",
                file=sys.stderr,
            )
            return 2
        if not args.samples_dir.is_dir():
            print(
                f"ERROR: --samples-dir is not a directory: {args.samples_dir}",
                file=sys.stderr,
            )
            return 2
        wav_files = [p for p in args.samples_dir.glob("*.wav") if p.is_file()]
        if not wav_files:
            print(
                f"ERROR: --samples-dir {args.samples_dir} contains no .wav files.",
                file=sys.stderr,
            )
            return 2

    if args.asr_input is not None and not args.asr_input.exists():
        print(f"ERROR: --asr-input not found: {args.asr_input}", file=sys.stderr)
        return 2

    if args.speakers > 1 and args.asr_input is None:
        print(
            "ERROR: --speakers > 1 only meaningful in ASR mode (needs --asr-input)",
            file=sys.stderr,
        )
        return 2
    if args.diarize and args.asr_input is None:
        print(
            "ERROR: --diarize only meaningful in ASR mode (needs --asr-input)",
            file=sys.stderr,
        )
        return 2
    if args.min_speakers < 1 or args.max_speakers < args.min_speakers:
        print(
            f"ERROR: --min-speakers ({args.min_speakers}) must be >= 1 and "
            f"<= --max-speakers ({args.max_speakers})",
            file=sys.stderr,
        )
        return 2

    # --asr-prompt None (unset) -> use the F1 default; "" -> disable.
    if args.asr_prompt is None:
        asr_prompt: str | None = DEFAULT_F1_ASR_PROMPT
    elif args.asr_prompt == "":
        asr_prompt = None
    else:
        asr_prompt = args.asr_prompt

    # Resolve backend + model. Only matters in ASR mode, but harmless
    # otherwise (synthesize ignores them unless --asr-input is set).
    if args.asr_backend == "auto":
        asr_backend = select_asr_backend()
    else:
        asr_backend = args.asr_backend
    asr_model = resolve_asr_model(args.asr_model, asr_backend)

    try:
        outputs = synthesize(
            args.voice_stem,
            args.background_stem,
            args.samples_dir,
            args.pitch_offset,
            args.rate_hz,
            args.asr_input,
            asr_model,
            args.speakers,
            args.speaker_spread,
            args.diarize,
            args.min_speakers,
            args.max_speakers,
            asr_prompt,
            asr_backend,
        )
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print("[spike-b] done:", {k: str(v) for k, v in outputs.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
