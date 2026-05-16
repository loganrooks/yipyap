# Lessons

Durable takeaways from spike work and Phase 1+ implementation. Each
entry is **non-Phase-specific**: anything only useful inside one
particular spike stays in `spikes/<NN>-<topic>-findings.md`.

A lesson moves here when someone has decided it should inform future
work even after the originating code is gone. Reference the source so a
reader can trace it back.

## L001 — Animalese letter samples carry intrinsic static

**Origin:** Spike B baseline analysis, 2026-05-16.
**See:** `spikes/02-synthesis-log.md` baseline entry,
`spikes/02-synthesis-findings.md`.

The animalese.js bank we extract from ships as PCM_U8 (8-bit unsigned,
~48 dB intrinsic SNR), so quantization hash is baked into the sample
data before our pipeline touches it. Several pipeline behaviours
amplify or expose that hash:

- Per-letter peak-normalization (in `spikes/00_extract_bank.py`) raises
  the noise floor of quiet letters along with the signal.
- Linear-interpolation pitch-shift (`np.interp` in
  `02_synthesis.py:pitch_shift_from_to`) has no anti-aliasing; upward
  shifts (e.g. `--pitch-offset 12` ≈ 2× speed) fold 4–8 kHz content
  into 0–4 kHz as aliased garbage.
- Several letters ship with measurable DC offsets (`f` at −0.143
  versus a typical ±0.015); short edge fades only partially mask the
  boundary step at placement time.
- A fixed-cutoff bank LPF (currently 4.5 kHz) can mask quant hash above
  the cutoff but cannot remove fricative-band hash (4–8 kHz) without
  killing fricative identifying energy.

**Implication for Phase 1+:** treat the sample bank as *noisy input*
and the pitch-shift + placement chain as *potentially noise-amplifying*.
Specific mitigations and their outcomes track in the spike log; the
ones that work get promoted into additional lessons here.
