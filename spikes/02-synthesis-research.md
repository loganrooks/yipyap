# Spike B — open-source animalese implementations survey

> Companion to `02-synthesis-plan.md`. Informs E7 (re-source the bank).
> Goal: characterize what other people have done with animalese samples
> so we can decide whether re-sourcing is feasible and what to pick.

## 1. Forks of `Acedio/animalese.js`

`Acedio/animalese.js` has **54 forks** ([list][acedio-forks]). I scanned
all of them; none modify `animalese.wav`. Every fork ships the identical
SHA `6eca39…a5da` blob (PCM_U8, 44.1 kHz, mono, ~3.9 s, 26×0.15 s, CC BY 4.0
per [LICENSE.md][acedio-license]).

> **How verified** (2026-05-16): `gh api repos/acedio/animalese.js/forks
> --paginate --jq '.[].full_name'` enumerated the 54 forks; for each,
> the bank file at `animalese.wav` was checked via
> `gh api repos/<fork>/contents/animalese.wav --jq .sha`. All returned
> the same blob SHA `6eca39…a5da` as upstream. The pagination cursor
> was exhausted (no further pages) at the time of the query — there
> may be forks created after that date that this audit doesn't cover.

The only fork worth flagging:

- **[Wexx/animalese.js-text-animation][wexx]** — adds a typewriter visualizer;
  same bank. License: not declared on the fork. **Interesting for us:** no — bank unchanged.

The forks all touch the JS wrapper or demo page; nobody re-sourced the bank.
**This is the negative finding.** If anybody had fixed the static at the
source we'd have seen it here.

## 2. Independent ports / re-implementations

### Same bank as acedio (PCM_U8 reuses)

- **[jakubpetrik/animalese-swift][jakub]** — direct Swift port of acedio's
  algorithm. Ships the same `animalese.wav` (referenced via `NSDataAsset`).
  License: not declared. **Interesting:** confirms acedio's algorithm
  exactly; useful as a reference for the bit-for-bit byte indexing logic.

### Distinct re-recorded English-letter banks

- **[equalo-official/animalese-generator][equalo]** (Python, MIT) — 4 pitch
  banks (`high`/`med`/`low`/`lowest`), 26 letters each plus `sh`/`th`/`.`.
  Per-letter wavs: **16-bit PCM, mono, 44.1 kHz, ~0.257 s**. So already
  16-bit (vs acedio's U8). Processing: per-letter peak-norm; random
  ±0.35-octave pitch jitter; pitch-shift via `frame_rate` trick (no
  anti-aliasing). Letter origin not documented — most likely sourced
  from an early ACGC voice rip. **Interesting:** already 16-bit at our
  target SR, redistributable under MIT, 4 personality-ish variants. Strong
  E7 candidate if the sound is acceptable.

- **[27Aditi/animalese-speech-synthesizer][aditi]** (Python, MIT) — ships
  the **same 26 wav blobs** as equalo (identical SHA on `sound01.wav`).
  License: MIT. **Interesting:** confirms equalo's bank is the de-facto
  community 16-bit alternative; widely cloned but small-scale.

- **[graysonpike/animalese][grayson]** (C++, MIT) — ships **235 wav files**
  from the New Horizons "Kiza" (snooty) personality, named
  `Voice_Kiza_Kana_*` and `Voice_Kiza_KanaEx_*`. Each is
  **16-bit PCM, stereo, 48 kHz, ~0.16 s**. These are *game-extracted*
  syllable samples (kana + kana-extensions: ka, ki, ku, ke, ko, kya,
  kyo, gwa, swi, tswi, etc. — 92-phoneme architecture). Repo's own code
  uses only ~26 of them. Processing: miniaudio pitch-shift + minor
  random pitch variation. **Interesting:** the most accurate publicly
  redistributed sample bank we've seen — full kana coverage from the
  actual game audio. Repo MIT-licensed; the samples are clearly
  Nintendo-derived (legal note below).

- **[macstudents/Animalese-Generator][macstudents]** (C#, no LICENSE file) —
  the most ambitious bank: per-vowel × per-MIDI-pitch samples for
  Boy/Girl/Man/Woman personalities (`Npc_Vocal_*` naming, e.g.
  `Npc_Vocal_Boy_A_60`, `Npc_Vocal_Girl_E_64`, etc.). **16-bit PCM, mono,
  48 kHz, ~11 s each.** README explicitly says "extracted from the
  *Animal Crossing: New Horizons* ROM" using
  [bars-to-bwav][bars2bwav] + [Switch-Toolbox][switch-toolbox].
  **Interesting:** this is the closest to "raw game samples" anyone
  ships publicly. Multi-personality, MIDI-pitch grid. Legal status:
  almost certainly *not* redistributable cleanly (Nintendo IP, no
  license declared on the repo, no claim of fair use).

- **[DigiDuncan/animalese.py][digiduncan]** (Python, GPL-3) — three banks:
  `english/` (26 letters, **16-bit/44.1 kHz/0.15 s mono**), `english-old/`
  (16-bit/16 kHz mono — looks like an old TTS-style bank), and
  `japanese/` (~70 kana, 16-bit/16 kHz mono). Processing: pydub
  `fade` and `overlay` for stitching, no explicit dither / DC handling.
  Includes acedio's `animalese.wav` for backward compat. **Interesting:**
  the only repo with a Japanese-kana bank shipped that isn't game-derived.

- **[joshxviii/animalese-typing-desktop][joshx]** (Electron, MIT) — ships
  `f1-f4` (female), `m1-m4` (male) voices in English + Korean. **Ogg
  Vorbis, mono, 48 kHz, ~120 KB each.** Each `.ogg` is a sprite-strip
  containing all letters concatenated (~3-4 s each). Used as upstream
  for the [`animalese` Rust crate][rust-crate] (also MIT). **Interesting:**
  cleanest license-tracked multi-voice bank; 8 voices × 2 languages.
  Origin of the recordings not documented but the README claims them as
  original assets.

- **[brsgr/animalese-generator][brsgr]** (JS, no LICENSE) — *no fixed bank*;
  user records their own 26 letters via mic, then applies user-configurable
  speed / pitch-shift / distortion / HPF / LPF / compression via Web Audio.
  **Interesting:** validates the user-letter-record UX as plausible;
  irrelevant to our bank-choice problem, but a clean reference for
  what Web Audio processing chain "everyone" reaches for.

- **[alialhasnawi/animal][ali]** (JS, MIT) — single voice, **Ogg Vorbis,
  mono, 48 kHz**, includes digraphs (`ch`/`sh`/`th`/`oo`). Hand-recorded
  English. **Interesting:** small bank with digraph awareness; demonstrates
  digraph approach if we ever want it.

- **[Wally869/Animalise][wally869]** (JS) — inlines MP3 data-URIs from a
  YouTube tutorial author's recordings. Quality is explicitly disclaimed
  ("Base sounds are not the best quality"). **Interesting:** mostly a
  cautionary tale that you can build a working animalese demo from
  arbitrary low-quality syllable mp3s.

## 3. Game-extracted samples

Yes — extracted to varying degrees. **`graysonpike` (Kiza/snooty, NH)** and
**`macstudents` (Boy/Girl/Man/Woman, NH)** above both ship them. Tools
documented:

- **Switch / NH:** `.bars` containers → `.bwav` via
  [`jackz314/bars-to-bwav`][bars2bwav] or [`K-E-R-A-D/BARcSharp`][barcsharp]
  → `.wav` via `vgmstream`. Samples live in the `Doubutsugo` container.
  Personality file naming: `Voice_<personality>_Kana_<syllable>` (e.g.
  `Kiza`, `Boy`, `Girl`, etc.). The fan-archive thread
  ([VG Resource thread-37422][vgr-37422]) describes the full extraction.
- **GCN:** decomp project [`ACreTeam/ac-decomp`][ac-decomp] (100%
  matching) confirms the audio engine is `jaudio_NES` (a.k.a. neos,
  JaiSeq-adjacent). Per [hcs64 forum][hcs64]: VADPCM, 32 kHz, 4-bit/9-byte
  window. No public clean rip of GCN animalese banks specifically.
- **DS / Wild World:** [The Sounds Resource][tsr-acww] hosts ripped
  voice rips; Nookipedia notes WW animalese is per-letter random-syllable
  (not phoneme-aware) due to DS limits.

**Engine-level confirmation: multiple banks, not one bank pitch-shifted.**
This was the open question. The file naming and macstudents' README
confirm: each personality (Kiza, Boy, Girl, Man, Woman, …) has its own
recorded sample set, not a pitch shift of a single shared bank. Nookipedia
backs this: New Leaf added per-personality voices, and New Horizons has
distinct `Voice_<personality>_*` files. The "single bank + pitch shift"
folk explanation is wrong above the personality level; it's only true
*within* a personality (e.g. excited speech raises pitch of that
personality's bank).

**Legal frankness:** Anything tagged `Npc_Vocal_*`, `Voice_Kiza_*`,
`Voice_<personality>_*` is Nintendo audio. Redistributing it without
license is the standard ROM-rip grey zone: tolerated by community
archives (VG Resource, TCRF), not safe for a shipped project. We can
*study* it locally; we should not bundle it. The clean route for
yipyap is acedio's CC BY 4.0 bank or a freshly-recorded original.

## 4. Technical writeups

- **[Nookipedia Animalese][nookipedia]** — best fan-research summary.
  Key claim: **92 phonemes** in the actual engine (69 kana + 18
  English-only sounds + 10 digits + 5 sung). New Leaf added per-personality
  pitches; New Horizons added per-personality recordings. No citations
  to primary source but matches the macstudents/graysonpike file
  naming.
- **[The Cutting Room Floor (TCRF)][tcrf-ac]** — has Animal Crossing
  pages for every entry but **no dedicated animalese section** that I
  could find. Useful for unused voices generally; no animalese-specific
  primary docs.
- **[hcs64 forum: AC GCN JaiSeq][hcs64]** — most detailed GCN-era
  technical thread: VADPCM, 32 kHz, sample tuning floats per
  instrument. Animalese specifically isn't broken out.
- **[ACreTeam/ac-decomp][ac-decomp]** — 100% matching GCN decomp; the
  audio engine source is in `src/static/jaudio_NES/`. The animalese
  pitch-and-stitch logic is in there if we want primary-source truth
  for the GCN, but reading 10k LOC of decompiled Nintendo audio
  middleware is a research project in itself.
- **YouTube — ["How to make Animalese" tutorial][yt-tutorial]** (linked
  from Wally869) is the source of several JS implementations' samples.

## 5. Audio cleanup tricks others apply

Reading the actual code of every implementation cited in sections 1–4
above (acedio, jakubpetrik/animalese-swift, 27Aditi/animalese-python,
graysonpike/animalese-py, brsgr/animalese-rs, equalo's, DigiDuncan's,
and joshxviii's repos — each cloned and read at the commits referenced
by their respective sections of this doc, 2026-05-16):

- **Per-letter edge fades:** universal. `equalo` does it implicitly via
  pydub; `graysonpike` via miniaudio; `27Aditi` does explicit
  `np.linspace` 10 ms linear fades.
- **Per-letter peak-norm to a constant:** `27Aditi` (to int16 max).
  Nobody does bank-wide peak-norm (our E1b). **Gap we're filling.**
- **Random pitch jitter for variety:** universal (`graysonpike`,
  `equalo`, joshxviii, brsgr). Range ±0.25–0.35 octaves typical.
- **Anti-aliased pitch shift (E4):** **nobody.** Every implementation
  pitch-shifts by changing `frame_rate` or by linear `np.interp`, no
  pre-LPF, no polyphase. The Rust crate uses `kira` which has
  click-free fades but standard resampling. **Gap we're filling.**
- **Dither on re-quantize (E2):** **nobody.** Every implementation
  reads U8 or 16-bit and writes 16-bit without dither. **Gap.**
- **DC removal (E1a):** **nobody** does it explicitly. **Gap.**
- **Equal-power crossfade (E5):** **nobody.** Linear fades everywhere.
  **Gap.**
- **Stitching strategy:** roughly two camps. (a) concat with small
  overlap (`graysonpike`, `equalo`); (b) `overlay` at fixed time offsets
  with per-letter fade-out (`DigiDuncan` does 5 ms fade to −12 dB at
  the tail) — psychoacoustically smoother but loses transient punch.

**Net:** the E1–E5 stack in `02-synthesis-plan.md` is genuinely past
the state of the open-source art. We are not re-inventing — we're
adding the audio-engineering layer nobody bothered with because their
use case (a Discord bot, a typing toy) didn't expose the artifacts.
Ours does, because the output sits on top of stereo broadcast audio
where stitch artifacts are audible.

## If E7 happens, what to pick

**Tiered recommendation.**

1. **Tier 1 (clean, default):** stay on acedio's `animalese.wav` and
   resample/dither it up to 16-bit at extract-time before slicing. E2
   already does this — E7 mostly becomes "document that the U8 source
   is the hard floor and we lifted it." CC BY 4.0, redistributable,
   reproducible, no IP risk. **This is the conservative pick.**
2. **Tier 2 (better, still clean):** adopt the **equalo bank** as an
   alternative. 16-bit, 44.1 kHz, MIT, 26 letters × 4 pitch variants —
   maps cleanly onto our extract → slice → render pipeline with no
   contract changes. Listening-test required to confirm character is
   AC-enough. If yes, ship a `--bank=equalo` flag and keep acedio as
   default. Cost: ~1 day of integration + listening.
3. **Tier 3 (best fidelity, NOT shippable):** for *internal study only*,
   audit our outputs against **graysonpike's Kiza bank** (16-bit,
   48 kHz, real-game samples) to see what the upper bound sounds
   like. Do not bundle. Use as a "ground-truth listening reference"
   in `docs/listening-log.md`.
4. **Tier 4 (record original):** if Tier 1 + Tier 2 both fail the
   listening bar after E1–E5, record a fresh original 26-letter bank
   (one English voice, ~5 minutes of studio time) at 24-bit/48 kHz,
   CC0 / our copyright. ~half-day of work for a Phase-1 maintainer
   with a quiet room. This is the durable answer if AC aesthetic
   without IP risk is the real constraint.

**My recommendation:** run E1–E5 on acedio first. If the hybrid stack
still fails the static rubric, do E7 = swap to **equalo** (Tier 2)
behind a flag and re-test. Don't jump to recording original samples
until both fail.

## Open questions / things I couldn't find

- **GCN/Wild World animalese banks specifically.** No public clean rip
  isolates just the animalese syllables (vs general voice SFX) for the
  GCN or DS games. Decomp source has the pitch logic but extracting the
  raw VADPCM by hand is a project.
- **Provenance of `equalo`'s 4 pitch banks.** Nobody documents whether
  these are re-recorded, pitch-shifted variants of one source, or
  partially game-derived. Worth a listen comparison before trusting MIT.
- **Whether anyone uses formant-corrected pitch shift.** Everyone does
  speed-and-pitch coupled. Nobody decouples (e.g. via phase vocoder or
  WORLD). Probably out of scope, but it's the obvious next-tier fix
  beyond E4.
- **A genuinely free, AC-aesthetic, well-documented bank.** Doesn't seem
  to exist. The closest is acedio's (CC BY 4.0 but PCM_U8) and equalo's
  (MIT, 16-bit, but undocumented provenance). Both are compromises.
- **Whether the static is mostly bank-floor or pipeline.** Surveying
  these implementations didn't answer this — we still need our own
  measurements. Mild surprise: I expected at least one fork to have
  fought this battle; none did.

[acedio-forks]: https://github.com/Acedio/animalese.js/network/members
[acedio-license]: https://github.com/Acedio/animalese.js/blob/master/LICENSE.md
[wexx]: https://github.com/Wexx/animalese.js-text-animation
[jakub]: https://github.com/jakubpetrik/animalese-swift
[equalo]: https://github.com/equalo-official/animalese-generator
[aditi]: https://github.com/27Aditi/animalese-speech-synthesizer
[grayson]: https://github.com/graysonpike/animalese
[macstudents]: https://github.com/macstudents/Animalese-Generator
[digiduncan]: https://github.com/DigiDuncan/animalese.py
[joshx]: https://github.com/joshxviii/animalese-typing-desktop
[rust-crate]: https://crates.io/crates/animalese
[brsgr]: https://github.com/brsgr/animalese-generator
[ali]: https://github.com/alialhasnawi/animal
[wally869]: https://github.com/Wally869/Animalise
[bars2bwav]: https://github.com/jackz314/bars-to-bwav
[barcsharp]: https://github.com/K-E-R-A-D/BARcSharp
[switch-toolbox]: https://github.com/KillzXGaming/Switch-Toolbox
[vgr-37422]: https://archive.vg-resource.com/thread-37422.html
[tsr-acww]: https://www.sounds-resource.com/ds_dsi/acww/sound/1734/
[ac-decomp]: https://github.com/ACreTeam/ac-decomp
[hcs64]: https://hcs64.com/mboard/forumlong.php?showthread=64579
[nookipedia]: https://nookipedia.com/wiki/Animalese
[tcrf-ac]: https://tcrf.net/Animal_Crossing:_New_Horizons
[yt-tutorial]: https://www.youtube.com/watch?v=t_jFVcA-ZsQ
