# Spike B — josh's animalese bank: source audit + port plan

> Companion to `02-synthesis-research.md` (which covered josh at the
> bank level). This is the deep dive: how the pipeline works, what each
> voice measures, where the audio came from, what it takes to adopt.
>
> Extracted: `spikes/samples-josh-{f1..f4,m1..m4}/` plus
> `samples-josh-korean-f1/`. 26 letters × 9 voices × 200 ms @ 44.1 kHz
> mono 16-bit, peak-normed 0.95. All dirs pass count/peak/DC sanity.

## §1 — How josh's generation actually works

Audited: `main.js`, `preload.cjs`, `utils/keycode-to-sound.cjs`,
`utils/audio-manager.cjs`, `renderer/animalese.cjs`.

A native key-listener binary emits JSON events (`main.js:430-451`).
Keycodes map to paths like `&.a`, `%.60`, `sfx.enter`
(`keycode-to-sound.cjs:11-100`). Each event dispatches into
`playSound(path, options)` (`audio-manager.cjs:197`); Howler plays.

**Pitch formula** (`audio-manager.cjs:297-299`):

```js
const finalPitch = (note - 60) + pitchShift + (Math.random()*2-1.0)*pitchVariation;
const rate = Math.pow(2, finalPitch / 12.0);
bank.rate(rate, id);
```

So `rate = 2^(semitones/12)`. For voice, `(note - 60) = 0`, leaving
`semitones = pitchShift + uniform(-1, +1) * pitchVariation`. `bank.rate()`
is Howler's Web Audio playbackRate — **time-domain resample, no
anti-alias filter**. The author *knows* this; the very first lines of
`audio-manager.cjs:1-2` are a TODO to replace Howler for this exact
reason. In practice, default variation = 0.2 keeps rate within
[0.988, 1.012]; yelling pushes to ~1.09. Aliasing risk is theoretical
only — content is mostly < 8 kHz at SR 48 kHz.

**Yelling** (`renderer/animalese.cjs:117-120`) triggers on `CapsLock
XOR Shift`. Effect (`audio-manager.cjs:233-240`):

```js
volume         = yelling ? .75 : .65;
pitchShift     = (yelling ? 1.5 : 0) + voice_profile.pitch;
pitchVariation = (yelling ? 1   : 0) + voice_profile.variation;
```

So yelling = +1.5 st pitch + 1.0 st variation + 0.10 louder. **Not
just pitch** — common AI-summary failure mode.

**Per-letter jitter:** `Math.random()*2-1.0` is uniform [-1, +1] ×
`pitchVariation`. Default ±0.2 st (subtle), yelling ±1.2 st (audible).
**Uniform, not Gaussian. Math.random() — unseeded.**

**Intonation ramp** (`audio-manager.cjs:155-178`): **3200 ms ramp** over
64 steps, asymmetric end-rate (positive can triple rate; negative uses
softened sqrt), `setTimeout`-driven geometric interpolation. Default
`ramp=2` (ease-out). Designed for held instrument notes — for 200 ms
voice letters, only ~6% of the ramp fires before the sound ends.
**Effectively dormant for typing-mode voice playback.** If an AI summary
called this "fast per-letter pitch sweep," that's wrong — it's a slow
whole-sound ramp.

**Sprite layout** (`audio-manager.cjs:27-68`): a-z at 200 ms × 26
(5.2 s), then 0-9 × 200 ms (2.0 s), then `ok/gwah/deska` × 600 ms
(1.8 s). Total 9.0 s, matches file duration.

## §2 — Bank characterization

Stats from extracted wavs, DC-subtracted, peak-normed 0.95. `raw_peak`
is pre-norm peak (the real loudness signal). f0 via `librosa.pyin`
(`fmin=80, fmax=600`); range is across-letter median range, not
within-letter.

| voice | rms_mean | hf>5k | raw_peak | f0 med Hz | f0 range | character |
|-------|---------:|------:|---------:|----------:|---------:|-----------|
| josh f1 | 0.348 | 0.231 | 0.299 | 396 | 386–409 | high female, peppy, AC "Peppy" archetype |
| josh f2 | 0.294 | 0.255 | 0.360 | 485 | 474–495 | very high, almost squeaky |
| josh f3 | 0.267 | 0.298 | 0.361 | 345 | 335–352 | medium-high, breathy |
| josh f4 | 0.342 | 0.212 | 0.302 | 335 | 327–341 | medium female, warm |
| josh m1 | 0.258 | 0.224 | 0.399 | 383 | 368–389 | high male / kid voice |
| josh m2 | 0.274 | 0.238 | 0.365 | 351 | 345–357 | medium male, generic |
| josh m3 | 0.330 | 0.242 | 0.309 | 309 | 306–312 | medium-low, "Cranky" candidate |
| josh m4 | 0.227 | 0.070 | 0.351 | 100 | 98–359 (\*) | bass; very low HF; needs pitch-correction |
| josh kor-f1 | 0.379 | 0.224 | 0.283 | 396 | 384–406 | mirrors English f1 |
| acedio (baseline) | 0.235 | 0.242 | n/a | 256 | 234–306 | reference, U8 |
| equalo (mid) | 0.274 | 0.043 | n/a | 80 (\*\*) | 80–80 | low; HF aggressively LPFed |

(\*) m4's wide range is real (bass voice); pyin octave-doubles `q`/`y`
and `l` is unvoiced. Our existing outlier→median correction
(`02_synthesis.py:251-253`) handles this at load — no special-case code
needed.
(\*\*) equalo reads 80 because that's pyin's fmin clamp; bank is
pitched below 80 Hz.

**Anomalies: none.** Every dir has exactly 26 wavs, peak ≤ 0.99 (all at
0.95 post-norm), no silent letters, |DC| < 0.002. m4 has the lowest HF
content (0.070 vs 0.21–0.30 elsewhere), consistent with a relaxed bass.

Full per-letter detail: `/tmp/josh_stats_full.txt` (regen via
`.venv-spikes/bin/python /tmp/stats_josh.py`).

## §3 — Provenance

**Verdict: not clean.** Three pieces of evidence:

**Documentation:** README links a YouTube demo but never claims audio
authorship. No `CREDITS` / `ATTRIBUTION` / `ASSETS.md`. The MIT
`LICENSE` covers code, not assets — standard open-source legal gap.

**Git history** (unshallowed at `git fetch --unshallow`):

- `2732629` (2025-02-09, "Added files from extension version") imports
  audio under `src/assets/audio/animalese/female/voice_1..4/{a..z,Deska,
  Gwah,OK}.aac` and `male/voice_1..4/...` — **366 files, originally
  per-letter AAC**, organized like a *rip*, not a fresh recording.
- `4e6df93` (2025-04-21) concatenates AACs into the sprite-strip `.ogg`
  we see today, deletes originals.
- `c106cd0` (2025-04-29) adds `.wav` intermediates of `f1_voice.wav`
  etc. (and removes them in the same commit — odd if these were
  original recordings, normal if they're staging for ogg encode).
- `b17e3cb` (2025-12-17) adds Korean.

**The "Added files from extension version" commit** is the smoking gun:
this desktop repo did not produce the audio; an upstream extension did.
The `female/voice_1..4` + `male/voice_1..4` naming **mirrors AC: New
Horizons' personality-voice file convention** (Peppy/Snooty/Normal/
Big-Sister × Boy/Lazy/Cranky/Smug, per the macstudents bank and
bars-to-bwav docs cited in `02-synthesis-research.md:106-141`). The 8
voices × 2 languages structure and 48 kHz source SR match NH's
extraction profile.

**Empirical sanity check:** is josh f1 just acedio upsampled?
Cross-correlated josh-f1 vs acedio at common SR
(`/tmp/compare_josh_acedio.py`): mean xcorr **0.045**, max 0.18.
Same-recording correlation would be > 0.7. **Definitively different
recordings.** josh is fundamentally different content — different f0
(396 vs 256 Hz), different formants.

**Honest uncertainty:** I cannot prove the audio is game-extracted. I
can say:
1. No documentation of origin.
2. Naming + structure + format strongly suggest a NH-extracted lineage.
3. Definitely not acedio-derived.
4. *Could* be josh's own recordings deliberately mimicking NH
   conventions — unlikely (Occam), not impossible.

**Treat as Nintendo IP until proven otherwise.** MIT on the wrapper
repo is not legal cover for embedded game audio. The clean paths for
shipping yipyap remain: (a) acedio's CC BY 4.0, or (b) record original.

## §4 — Yipyap port plan

### §4.1 Layer A — drop-in bank swap

josh's 200 ms letters slot into our pipeline **with zero code
changes**:

| our constant | value | conflict? |
|--------------|------:|-----------|
| `00_extract_bank.py:35 LETTER_DURATION_S = 0.15` | acedio-specific | irrelevant; josh doesn't use this script |
| `02_synthesis.py:88 SAMPLE_PLACEMENT_MAX_S = 0.300` | onset-mode cap | OK — 200 ms < 300 ms |
| `02_synthesis.py:568 LETTER_MAX_S = 0.150` | ASR-mode render slice | OK — slicer takes first 150 ms of 200 ms source; tail discarded |

`02_synthesis.py:198-263 load_samples_bank` is **already
duration-agnostic** — globs `*.wav`, loads, LPFs at 4.5 kHz, estimates
pitch, median-corrects outliers. Just point `--samples-dir` at
`spikes/samples-josh-f1/`. It works today, no patch needed.

**The `--bank` flag is sugar:** add at `02_synthesis.py:1261` a
`--bank {acedio,josh-f1,...}` that resolves to `spikes/samples-<bank>/`
when `--samples-dir` is unset. ~15 LOC.

**Don't extend `00_extract_bank.py`** — it's coupled to acedio's URL/
PCM_U8/150 ms layout and serves as documentation of that source's hard
floor. Ship a sibling `00_extract_bank_josh.py` (promote
`/tmp/extract_josh.py` from this venture). Keeps the two extractors
independently versioned.

**Edge case worth noting:** josh m4's bass register (~100 Hz) means
even after `--pitch-offset +12` we end at ~200 Hz, below F1 commentator
range. m4 will need `+24` or be relegated to "low-register character"
roles. f1/f4 are the safer defaults for the typical broadcast pitch.

### §4.2 Layer B — port josh's features

| feature | where in yipyap | LOC | port? |
|---------|-----------------|----:|-------|
| Per-letter ±N st uniform jitter | `render_word` per-char loop (`02_synthesis.py:705-720`) | ~5 | **YES** — fills a known gap |
| Composite yelling mode | new + per-word RMS trigger | ~30 | MAYBE — needs prosody from ASR |
| Long intonation ramp | `render_word` per-word slope | ~25 | **NO** — sized for held notes, not 200 ms letters |
| Per-letter volume jitter | `render_word` per-char gain | ~5 | optional polish |

**Pitch jitter is the highest-value port** — current renderer plays the
same letter at the same pitch every repeat (mechanical). Add
`--pitch-jitter SEMITONES` (default 0.2 per josh; 1.0 for "yelling").
In the per-char loop at `02_synthesis.py:709`, sample
`jitter = rng.uniform(-j, +j)` and pass adjusted `target_hz` into
`pitch_shift_from_to`.

**Yelling** in our model maps to **high-RMS voiced regions** in source.
We already compute per-word pyin pitch (`02_synthesis.py:1007-1011`);
add per-word RMS and trigger composite (pitch +1.5, jitter +1.0, vol
+10%) above threshold. Genuinely useful for F1 ("MAGIC MAX!" cues).
Worth a Layer B PR after Layer A ships.

**Skip intonation ramp.** Designed for 3.2 s held notes; we render
200-800 ms words. If we want per-word prosody, take the *idea* (curved
glide) and drive it from within-word pyin trajectory — separate
research direction, not "porting josh."

What we lose by skipping josh's full feature set: nothing perceptually
significant for offline-batch. josh's design is for live-typing
interactivity; we have richer prosody info (ASR + pyin) than keystroke
events provide, so we can do per-word effects from real data.

## §5 — Record-your-own plan

Load-bearing given §3.

**Take list:** 26 letters (a-z) at one pitch. **Skip** 0-9 (we render
numbers as Whisper-spelled words), `ok/gwah/deska` (no terminal
punctuation render), Korean, instruments.

**Output format:** 26 wav, 44.1 kHz mono 16-bit, ~200 ms each,
DC-corrected + peak-normed 0.95. Same as our josh extraction; drops
into `samples-original/` with no pipeline change.

**Per-take guidance.** AC character is **slightly nasal, gibberish,
monotone with falling intonation cut mid-letter** — not enunciated
letter names, but quick consonant+vowel-onset cut short.

- Pitch: pick target (270 Hz for "normal," 390 Hz for josh-f1 peppy);
  hum it before each take; drift target ±2 st across 26.
- Plosives: pop filter or 30° off-axis for /p,b/; de-ess /f,v,s/. AC
  voices are soft — aim for soft articulation throughout.
- Mic: 6-8" with pop filter, SM57/58 dynamic is fine, condenser only
  if room is treated.
- 26 takes, one letter at a time; 3-4 takes per letter, pick winner.
- Character: slightly nasal (smile while speaking, raise tongue back),
  *don't enunciate "ay"* — vocalize "ahh"/"buh"/"kuh" and cut short.

**Software path:** Audacity 48 kHz/24-bit → comp best take per letter
→ export each as wav → adapt `/tmp/extract_josh.py` to read 26
standalones (instead of a sprite-strip) → A/B against josh-f1 in
`02_synthesis.py`.

**Effort:** ~3-4 hours total for a non-pro with $100 USB mic in a
quiet room (1-1.5 h recording, 1 h post, 30 min integration, ~1 h
listening + retake of 3-5 problem letters — `c`/`q`/`x` notoriously
hard). Less than the time to debug provenance + IP on josh's bank.
Performer matters more than gear; PhD-level listening discipline is
the threshold, not vocal training.

## §6 — Recommendation

**Ship-Monday: Layer A swap to josh f1 for spikes, keep acedio as the
committed default bank.** Rationale:
- josh f1 is **measurably the cleanest, most AC-canonical** voice in
  any OSS bank surveyed (§2 + your listening verdict).
- Adoption is **zero code change** today.
- Provenance risk is material at *ship time*, not *spike time*. For
  Phase-0 listening evaluation, this is research fair use.
- Layer B pitch jitter is higher-value per LOC than hunting for a
  better bank, and bank-agnostic.

**Three-more-weeks: record original at josh-f1 character target, port
Layer B pitch jitter, expose `--bank` flag with josh banks listed for
spike use only.** Rationale:
- 3-4 hours of recording buys clean provenance forever; Phase 1+
  ships yipyap we own end-to-end, no README asterisk.
- Recording *target* is josh-f1's character (we know it sounds right)
  but our own voice — AC aesthetic without Nintendo IP.
- Layer B (jitter + yelling) is the marginal upgrade past josh, worth
  porting once the bank is decided.

**Path I'd avoid: "swap to josh, ship under MIT, hope nobody asks."**
Short-term sound at the cost of long-term distributability. Don't.

---

### Reproducibility

- Extraction: `/tmp/extract_josh.py` (run with `.venv-spikes/bin/python`)
- Per-letter stats: `/tmp/stats_josh.py` → `/tmp/josh_stats_full.txt`
- josh vs acedio xcorr: `/tmp/compare_josh_acedio.py` (mean 0.045)
- josh repo state: `/tmp/josh` @ `fa8af5a`; audio imported at
  `2732629` (2025-02-09), sprites at `4e6df93` (2025-04-21), Korean at
  `b17e3cb` (2025-12-17).
- Output: `spikes/samples-josh-{f1..f4,m1..m4,korean-f1}/` —
  26 × 200 ms × 44.1 kHz mono PCM_16, peak 0.95.

### External references

- josh repo: https://github.com/joshxviii/animalese-typing-desktop
- josh extension YouTube demo:
  https://www.youtube.com/watch?v=wdxvKpUY7q8
- Howler `rate()` / Web Audio playbackRate (time-domain resample, no
  anti-alias):
  https://developer.mozilla.org/en-US/docs/Web/API/AudioBufferSourceNode/playbackRate
- AC:NH voice extraction tools: `bars-to-bwav`, Switch Toolbox — see
  `02-synthesis-research.md:106-141`.
