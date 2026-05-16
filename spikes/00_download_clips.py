"""Spike bootstrap: download F1 broadcast clips for Spike A/B testing.

Defaults to the three clips used during initial Spike B development —
30-second audio extracts from three different F1 race highlights on
YouTube, chosen for stressor variety:

- ``abu_dhabi_60-90``: early race (engines + clean commentary).
- ``italian_240-270``: mid-race (slipstream battles, mixed dynamics).
- ``monaco_420-450``: late race / podium territory (music swells,
  driver celebrations — useful for diarization stress-testing).

``spikes/inputs/`` is gitignored — these are public YouTube highlights
downloaded for local research use; don't redistribute the resulting
WAVs.

Run once per fresh checkout::

    python spikes/00_download_clips.py
    # or to a custom location:
    python spikes/00_download_clips.py --out /tmp/clips/
    # or with a custom manifest (one ``video_id|name|HH:MM:SS-HH:MM:SS`` per line):
    python spikes/00_download_clips.py --manifest my_clips.txt

Requires ``yt-dlp`` and ``ffmpeg`` on PATH (yt-dlp downloads, ffmpeg
extracts/cuts the audio).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Default manifest: the three clips used during Phase 0 Spike B development.
# Format: (youtube_video_id, output_name, "HH:MM:SS-HH:MM:SS" section).
DEFAULT_CLIPS: list[tuple[str, str, str]] = [
    ("S-LMSpzlnc0", "abu_dhabi_60-90", "00:01:00-00:01:30"),
    ("kGMp1Byuwto", "italian_240-270", "00:04:00-00:04:30"),
    ("ajzQj7bjSWE", "monaco_420-450", "00:07:00-00:07:30"),
]


def check_tools() -> None:
    missing = [t for t in ("yt-dlp", "ffmpeg") if shutil.which(t) is None]
    if missing:
        raise RuntimeError(
            f"Missing on PATH: {', '.join(missing)}. Install with `brew "
            f"install {' '.join(missing)}` (macOS) or `apt install "
            f"{' '.join(missing)}` (Debian/Ubuntu)."
        )


def parse_manifest(path: Path) -> list[tuple[str, str, str]]:
    """Parse a manifest file. One ``video_id|name|section`` per line."""
    entries: list[tuple[str, str, str]] = []
    for lineno, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3:
            raise ValueError(
                f"{path}:{lineno}: expected 'video_id|name|HH:MM:SS-HH:MM:SS', "
                f"got {line!r}"
            )
        entries.append((parts[0], parts[1], parts[2]))
    if not entries:
        raise ValueError(f"{path}: no clip entries found.")
    return entries


def download_clip(video_id: str, name: str, section: str, out_dir: Path) -> Path:
    """Download a single time-range as WAV. Returns the output path."""
    out_template = str(out_dir / f"{name}.%(ext)s")
    url = f"https://www.youtube.com/watch?v={video_id}"
    cmd = [
        "yt-dlp",
        "--quiet",
        "--no-warnings",
        "--no-progress",
        "-x",
        "--audio-format",
        "wav",
        "--audio-quality",
        "0",
        "--download-sections",
        f"*{section}",
        "--force-keyframes-at-cuts",
        "-o",
        out_template,
        url,
    ]
    print(f"[download-clips] {name}: {video_id} @ {section}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"yt-dlp failed for {name} (exit {result.returncode}):\n"
            f"  stdout: {result.stdout.strip()}\n"
            f"  stderr: {result.stderr.strip()}"
        )
    wav_path = out_dir / f"{name}.wav"
    if not wav_path.exists():
        raise RuntimeError(
            f"yt-dlp returned 0 but {wav_path} not found. Section format "
            f"might have changed, or the video is unavailable."
        )
    return wav_path


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Download F1 broadcast clips for Spike A/B testing."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("spikes/inputs"),
        help="Directory to write {name}.wav into. Default: spikes/inputs/",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help=(
            "Path to a manifest file (one 'video_id|name|HH:MM:SS-HH:MM:SS' "
            "per line, # comments OK). Default: built-in 3-clip manifest "
            "(abu_dhabi, italian, monaco)."
        ),
    )
    args = parser.parse_args(argv)

    check_tools()

    if args.manifest is not None:
        if not args.manifest.exists():
            print(f"ERROR: --manifest not found: {args.manifest}", file=sys.stderr)
            return 2
        clips = parse_manifest(args.manifest)
    else:
        clips = DEFAULT_CLIPS

    args.out.mkdir(parents=True, exist_ok=True)
    failures: list[tuple[str, str]] = []
    for video_id, name, section in clips:
        try:
            download_clip(video_id, name, section, args.out)
        except RuntimeError as exc:
            print(f"[download-clips] FAILED {name}: {exc}", file=sys.stderr)
            failures.append((name, str(exc)))

    print(
        f"[download-clips] done: {len(clips) - len(failures)}/{len(clips)} "
        f"clips in {args.out}/"
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
