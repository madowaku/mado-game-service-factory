# MGSF-M1.2 MusMus BGM Intake / License-Safe Audio Bridge

Status: **incubation / HOLD**. This is a parallel M1.2 track and does not
depend on, modify, or promote the Gua, screen-only or GameDev Skills PRs.

## Problem and narrow MVP

MusMus introduced loop-ready OGG downloads for 258 BGM tracks in October
2026. A game developer still needs to choose music, personally download it,
record official provenance, credit the composer/site, and manually prove the
loop behaves correctly in their Godot or Unity build.

This module generates a reviewable **metadata-only** intake package. It does
not download or collect tracks, read their audio frames, decode, fingerprint,
transcode, remix, train on, upload, or copy any sound. It does not include
MusMus music, fixtures containing real audio, or a redistributed catalog.

Official references (review updated terms before use):

- [MusMus BGM catalog](https://musmus.main.jp/)
- [MusMus music license](https://musmus.main.jp/info.html)
- [MusMus October 2026 update](https://musmus.main.jp/blog/news-2026-10-18/)
- [Godot 4.7 OGG importer](https://docs.godotengine.org/en/4.7/classes/class_resourceimporteroggvorbis.html)

MusMus allows commercial and non-commercial BGM use with proper credit.
It permits normal BGM fades/loops but restricts content-changing modification,
secondary distribution, and AI-based audio alteration/training. Its website
also places conditions on downloads, so download manually through the official
site after reviewing those conditions. Do not treat this document as a license
or permanent guarantee.

## Workflow

1. Listen on the MusMus website and manually select a candidate.
2. Manually download a track from its official site, following current terms.
3. Place a copy in *your own game project*, not this repository.
4. Fill out `fixtures/musmus/intake-example.json` with factual human-curated
   title, official webpage, local relative asset path and license acknowledgement.
5. Run:

   ```sh
   mgsf musmus-intake fixtures/musmus/intake-example.json \
     --project-root /path/to/your-game \
     --output-root evidence/musmus-intake
   ```

6. Inspect `intake-report.json`, `CREDITS-draft.txt`, `ENGINE-NOTES.md`.
7. Manually verify licensing, actual audio, cue transitions, loop boundaries,
   Godot/Unity import settings, game volume and final game credits.

Example manifest shape:

```json
{
  "schema_version": 1,
  "project": "Sample Game",
  "tracks": [
    {
      "id": "town-theme",
      "title": "Human-curated title",
      "source_page": "https://musmus.main.jp/",
      "audio_path": "assets/audio/musmus/town.ogg",
      "selected_by_human": false,
      "license_reviewed": false,
      "loop_mode": "unknown"
    }
  ]
}
```

Allowed `loop_mode`: `unknown`, `none`, `full`, `intro`.
For `intro`, an optional `loop_offset_seconds` is **a human-provided value**;
it is never guessed from raw tags. Unknown points are marked for manual review.
An OGG loop tagged in samples must not be mistaken for seconds.

## Evidence contract

The report has `release_gate=HOLD` **unconditionally**, even if every
metadata check passes. `READY_FOR_MANUAL_PLAYBACK` means only that required
metadata is present and a local path currently exists; it is not proof that the
file is a valid OGG, plays, loops correctly or is legally usable.

The tool checks only filesystem presence (not media contents). It denies
absolute/traversal paths, symlink paths, unapproved source hosts and duplicate
IDs. Draft credits cover human-selected entries only. The resulting files are
planning records, not proof of license ownership or engine playback.

No network calls or third-party MCP services are used in this stage. There is
no automatic integration into Audio Studio MCP or SonicProof. Future bridges
must explicitly preserve their read-only/manual-review boundary and must never
send MusMus audio to AI processing.

## Engine notes and promotion boundary

Godot 4.7 provides an OGG importer `loop` switch and seconds-based
`loop_offset`. MusMus OGG files may include `LOOPSTART`/`LOOPLENGTH`
Vorbis comments, but this tool has **not verified Godot automatically consumes
those tags**. Unity full-clip `AudioSource.loop` is not equivalent to
intro-plus-region looping. Start with a manual no-gap test, then consider a
separately verified engine-specific solution.

To move beyond HOLD, capture an actual engine-run playback check with manual
listening results, finalize in-game credit, record version/date of license
review, review game packaging to avoid standalone asset redistribution, and
pass a final human compliance check. Do not turn a synthetic or metadata-only
artifact into a release PASS.
