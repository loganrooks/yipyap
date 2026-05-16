#!/usr/bin/env bash
# Execute a spike script on a remote host, sync outputs back to here.
#
# Designed for the apollo (Apple Silicon, listening) <-> dionysus (Linux,
# CUDA, larger Whisper models) workflow: run the heavy work where the
# GPU lives, listen where the speakers are.
#
# Usage:
#   spikes/run-remote.sh 02_synthesis.py [args...]   # run + sync
#   spikes/run-remote.sh 01_separation.py [args...]
#   spikes/run-remote.sh --sync-only                 # just rsync outputs
#
# Path/host overrides (env):
#   YIPYAP_REMOTE_HOST=dionysus                              SSH alias
#   YIPYAP_REMOTE_PATH=workspace/projects/yipyap             relative to $HOME on remote
#
# Notes:
#   - The script assumes the input files referenced in args already exist
#     at the same paths on the remote (true after running the bootstrap
#     scripts 00_download_clips.py + 00_extract_bank.py there). It does
#     NOT push local inputs over before running.
#   - rsync runs without --delete: local-only files (e.g. apollo's own
#     renders) are preserved. Newer dionysus versions of shared paths win.

set -euo pipefail

REMOTE_HOST="${YIPYAP_REMOTE_HOST:-dionysus}"
REMOTE_PATH="${YIPYAP_REMOTE_PATH:-workspace/projects/yipyap}"

usage() {
  sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-2}"
}

SYNC_ONLY=false
case "${1:-}" in
  -h|--help) usage 0 ;;
  --sync-only) SYNC_ONLY=true; shift ;;
esac

if [ "$SYNC_ONLY" = false ]; then
  if [ $# -lt 1 ]; then
    echo "ERROR: expected SCRIPT.py [ARGS...] or --sync-only" >&2
    usage 2
  fi
  # Forward args verbatim via %q quoting so paths with spaces / special
  # chars survive the SSH boundary.
  printf -v REMOTE_CMD '%q ' "$@"
  echo "[run-remote] host=$REMOTE_HOST path=~/$REMOTE_PATH"
  echo "[run-remote] python spikes/${REMOTE_CMD}"
  ssh "$REMOTE_HOST" "cd ~/$REMOTE_PATH && . .venv-spikes/bin/activate && python spikes/${REMOTE_CMD}"
fi

echo "[run-remote] rsync spikes/output/ from $REMOTE_HOST ..."
mkdir -p spikes/output
# -a archive (preserve perms+times), -z compress over the wire, -h
# human-readable sizes. No --info=: macOS's bundled rsync 2.x doesn't
# support it. No --delete: keep local-only files (apollo's own renders).
rsync -azh --stats \
  "${REMOTE_HOST}:~/${REMOTE_PATH}/spikes/output/" \
  "spikes/output/" | tail -15
echo "[run-remote] done."
