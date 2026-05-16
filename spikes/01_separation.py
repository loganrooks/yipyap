"""Spike A — source separation across architecturally distinct methods.

Throwaway script. Runs one separation backend on a clip and writes voice +
background stems for human listening tests. See ``docs/spike-plan.md`` for
why we want three architecturally distinct methods (Demucs family, Open-Unmix
Bi-LSTM, MDX-Net via UVR) rather than several Demucs hyperparameter variants.

Usage::

    # Demucs family — default backend, preserves earlier invocations.
    python spikes/01_separation.py clip.wav
    python spikes/01_separation.py clip.wav --backend demucs --models htdemucs_ft

    # Open-Unmix (Bi-LSTM masking).
    python spikes/01_separation.py clip.wav --backend umx --models umxl

    # MDX-Net via audio-separator (UVR).
    python spikes/01_separation.py clip.wav \\
        --backend mdx --models UVR-MDX-NET-Inst_HQ_3.onnx

Outputs land under
``spikes/output/spike-a/<backend>-<model>/<clip-stem>/{voice,background}.wav``.
First invocation of each backend/model downloads its weights to its own cache
(Demucs → ``~/.cache/torch/hub``; Open-Unmix → ``~/.cache/torch/hub``;
audio-separator → ``/tmp/audio-separator-models``).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import soundfile as sf
import torch

SPIKE_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = SPIKE_DIR / "output" / "spike-a"

DEFAULT_DEMUCS_MODELS = ("htdemucs_ft", "mdx_extra")
DEFAULT_UMX_MODELS = ("umxl",)
# UVR-MDX-NET-Inst_HQ_3 is a strong vocal-isolation MDX-Net model. The
# audio-separator catalogue ranks it ~SDR 8.8 on vocals; for Phase 0 it is a
# reasonable single representative of the MDX-Net family.
DEFAULT_MDX_MODELS = ("UVR-MDX-NET-Inst_HQ_3.onnx",)


def _safe_model_dir(model_name: str) -> str:
    """File-system-friendly variant of a model name (strips extension)."""
    base = model_name
    for ext in (".onnx", ".ckpt", ".pth", ".yaml"):
        if base.endswith(ext):
            base = base[: -len(ext)]
    return base


def separate_demucs(model_name: str, input_path: Path) -> dict[str, float | str]:
    """Demucs family backend (hybrid transformer / MDX)."""
    from demucs.apply import apply_model
    from demucs.audio import AudioFile
    from demucs.pretrained import get_model

    out_dir = OUTPUT_ROOT / f"demucs-{model_name}" / input_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    model = get_model(model_name)
    model.cpu()
    model.eval()
    sr = int(model.samplerate)
    channels = int(model.audio_channels)

    wav = AudioFile(input_path).read(
        streams=0, samplerate=sr, channels=channels
    )  # (channels, samples)
    ref = wav.mean(0)
    wav = (wav - ref.mean()) / ref.std()

    t0 = time.perf_counter()
    sources = apply_model(
        model,
        wav[None],
        shifts=1,
        split=True,
        overlap=0.25,
        progress=False,
        device="cpu",
    )[0]
    elapsed_s = time.perf_counter() - t0
    sources = sources * ref.std() + ref.mean()

    stem_names = list(model.sources)
    if "vocals" not in stem_names:
        raise RuntimeError(
            f"demucs model {model_name!r} sources lack 'vocals': {stem_names}"
        )
    vocals_idx = stem_names.index("vocals")
    voice = sources[vocals_idx]
    background = sum(
        sources[i] for i in range(sources.shape[0]) if i != vocals_idx
    )

    sf.write(out_dir / "voice.wav", voice.detach().cpu().numpy().T, sr)
    sf.write(out_dir / "background.wav", background.detach().cpu().numpy().T, sr)

    duration_s = float(wav.shape[-1]) / sr
    return {
        "elapsed_s": elapsed_s,
        "duration_s": duration_s,
        "ratio": elapsed_s / duration_s if duration_s > 0 else 0.0,
        "sr": float(sr),
        "out_dir": str(out_dir),
    }


def separate_umx(model_name: str, input_path: Path) -> dict[str, float | str]:
    """Open-Unmix backend (Bi-LSTM masking on spectrograms).

    Uses ``openunmix.predict.separate`` with ``residual=True`` so the
    non-vocal energy is captured as a single ``residual`` stem instead of
    being dropped.
    """
    from openunmix import predict

    out_dir = OUTPUT_ROOT / f"umx-{model_name}" / input_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    audio_np, sr_in = sf.read(str(input_path), dtype="float32", always_2d=True)
    # audio_np: (length, channels). umx wants (channels, length) torch tensor.
    audio_t = torch.from_numpy(audio_np.T).contiguous()

    t0 = time.perf_counter()
    estimates = predict.separate(
        audio=audio_t,
        rate=sr_in,
        model_str_or_path=model_name,
        residual=True,
        device="cpu",
    )
    elapsed_s = time.perf_counter() - t0

    if "vocals" not in estimates:
        raise RuntimeError(
            f"umx model {model_name!r} did not produce a 'vocals' estimate. "
            f"Got keys: {list(estimates.keys())}"
        )
    voice_t = estimates["vocals"][0]  # (channels, length)
    if "residual" in estimates:
        background_t = estimates["residual"][0]
    else:
        bg = None
        for k, v in estimates.items():
            if k == "vocals":
                continue
            bg = v[0] if bg is None else bg + v[0]
        if bg is None:
            raise RuntimeError(
                f"umx {model_name!r}: cannot derive background — no "
                f"non-vocal stems in {list(estimates.keys())}"
            )
        background_t = bg

    sf.write(out_dir / "voice.wav", voice_t.detach().cpu().numpy().T, sr_in)
    sf.write(out_dir / "background.wav", background_t.detach().cpu().numpy().T, sr_in)

    duration_s = audio_np.shape[0] / float(sr_in)
    return {
        "elapsed_s": elapsed_s,
        "duration_s": duration_s,
        "ratio": elapsed_s / duration_s if duration_s > 0 else 0.0,
        "sr": float(sr_in),
        "out_dir": str(out_dir),
    }


def separate_mdx(model_name: str, input_path: Path) -> dict[str, float | str]:
    """MDX-Net backend via ``audio-separator`` (UVR's vocal-isolation models).

    The Separator writes outputs to ``output_dir`` using
    ``custom_output_names`` to map UVR's "Vocals" / "Instrumental" stems to
    our ``voice`` / ``background`` filenames.
    """
    from audio_separator.separator import Separator

    safe_name = _safe_model_dir(model_name)
    out_dir = OUTPUT_ROOT / f"mdx-{safe_name}" / input_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    sep = Separator(
        output_dir=str(out_dir),
        output_format="WAV",
        log_level=30,  # WARNING — suppress per-chunk progress noise
    )
    sep.load_model(model_filename=model_name)

    t0 = time.perf_counter()
    output_files = sep.separate(
        str(input_path),
        custom_output_names={
            "Vocals": "voice",
            "Instrumental": "background",
        },
    )
    elapsed_s = time.perf_counter() - t0

    # audio-separator writes ``<name>.wav`` (case may be platform-dependent on
    # case-sensitive file systems). Resolve glob-insensitively.
    def _resolve(stem: str) -> Path:
        for cand in out_dir.iterdir():
            if cand.is_file() and cand.stem.lower() == stem and cand.suffix.lower() == ".wav":
                return cand
        raise FileNotFoundError(stem)

    try:
        voice_path = _resolve("voice")
        background_path = _resolve("background")
    except FileNotFoundError:
        produced = sorted(p.name for p in out_dir.iterdir() if p.is_file())
        raise RuntimeError(
            f"mdx {model_name!r}: expected voice.wav and background.wav, "
            f"found {produced} (separate() returned {output_files})"
        )

    # Canonicalise to lowercase voice.wav / background.wav
    if voice_path.name != "voice.wav":
        voice_path = voice_path.rename(out_dir / "voice.wav")
    if background_path.name != "background.wav":
        background_path = background_path.rename(out_dir / "background.wav")

    info = sf.info(str(voice_path))
    duration_s = info.frames / float(info.samplerate)
    return {
        "elapsed_s": elapsed_s,
        "duration_s": duration_s,
        "ratio": elapsed_s / duration_s if duration_s > 0 else 0.0,
        "sr": float(info.samplerate),
        "out_dir": str(out_dir),
    }


BACKEND_DISPATCH = {
    "demucs": separate_demucs,
    "umx": separate_umx,
    "mdx": separate_mdx,
}

BACKEND_DEFAULT_MODELS = {
    "demucs": DEFAULT_DEMUCS_MODELS,
    "umx": DEFAULT_UMX_MODELS,
    "mdx": DEFAULT_MDX_MODELS,
}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Spike A — multi-backend source separation."
    )
    parser.add_argument(
        "input", type=Path, help="Source clip (mp3/wav/m4a/flac)."
    )
    parser.add_argument(
        "--backend",
        choices=list(BACKEND_DISPATCH.keys()),
        default="demucs",
        help="Separation backend family. Default: demucs.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=None,
        help=(
            "Model names to run for the selected backend. Defaults: "
            "demucs -> htdemucs_ft mdx_extra; umx -> umxl; "
            "mdx -> UVR-MDX-NET-Inst_HQ_3.onnx."
        ),
    )
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"ERROR: input not found: {args.input}", file=sys.stderr)
        return 2

    backend = args.backend
    models = tuple(args.models) if args.models else BACKEND_DEFAULT_MODELS[backend]

    print(f"[spike-a] input={args.input}")
    print(f"[spike-a] backend={backend}")
    print(f"[spike-a] models={list(models)}")
    print(f"[spike-a] torch.cuda.is_available()={torch.cuda.is_available()}")

    sep_fn = BACKEND_DISPATCH[backend]
    for model_name in models:
        print(f"\n[spike-a] running {backend}/{model_name} ...")
        try:
            info = sep_fn(model_name, args.input)
        except Exception as e:  # noqa: BLE001 — spike: surface anything that goes wrong
            print(
                f"[spike-a] {backend}/{model_name} FAILED: "
                f"{type(e).__name__}: {e}",
                file=sys.stderr,
            )
            return 1
        per_min = float(info["ratio"]) * 60.0
        print(
            f"[spike-a] {backend}/{model_name} done: "
            f"elapsed={info['elapsed_s']:.2f}s "
            f"duration={info['duration_s']:.2f}s "
            f"ratio={info['ratio']:.2f}x realtime "
            f"(~{per_min:.0f}s of compute per 60s of audio)"
        )
        print(f"[spike-a] stems -> {info['out_dir']}")

    print(f"\n[spike-a] outputs under {OUTPUT_ROOT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
