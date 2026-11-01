# MGSF Sound Identity Lab M0.5: Sound Director Intelligence (incubation)

This is a **free, local, deterministic review assistant**, not an automated composer or an expert judge. It uses standard-library MIDI interval 4-note n-grams, PCM WAV loop-seam sample differences, and human listening prompts. No generative model is called.

## Run

First safely import WAV through M0.2. Keep any user-exported MIDI files next to the director brief.

~~~bash
mgsf sound-director /path/to/godot sound-brief.json --output-root evidence/sound-director
# After a person listens and completes the generated review-template.json:
mgsf sound-director /path/to/godot sound-brief.json \
    --review completed-review.json --output-root evidence/sound-director-reviewed
~~~

Example brief (replace each destination with an **exact** filename from the imported sound_map.json):

~~~json
{
  "schema": "mgsf.sound_identity.director_brief.v0.5",
  "tracks": [
    {"role": "title", "destination": "res://audio/mgsf_sound_identity/title_ACTUAL16HEX.wav", "scene": "res://scenes/title.tscn", "midi": "title.mid"},
    {"role": "battle", "destination": "res://audio/mgsf_sound_identity/battle_ACTUAL16HEX.wav", "scene": "res://scenes/battle.tscn", "midi": "battle.mid"}
  ]
}
~~~

Supported roles: title, menu, exploration, puzzle, battle, boss, result, ending, ambient. A scene is **planned intent**, not proof it is wired to the music. MIDI is optional; missing MIDI yields unknown motif overlap, never an artificially low similarity. MIDI inputs must remain beneath the brief directory and may not be symlinks.

## Deterministic observations

**MIDI motif candidate**: bounded Standard MIDI Files (format 0/1, PPQ, at most 2 MiB and 32 tracks) are parsed without playing or running MIDI payloads. Running status, note-on, meta and sysex skips are supported. Percussion channel 10 is excluded. The densest track/channel becomes a rough melodic proxy; for simultaneous notes take the highest pitch. Consecutive 4-note sequences become 3-step pitch interval patterns. Comparison is intersection count divided by the smaller pattern-set size. Transpositions can match. Low overlap under 0.2 is a review prompt, **never** a definitive lack of musical identity. Harmony, rhythm and timbre are not measured.

**Loop seam candidate**: for whole-file WAV loop requests, compare the normalized amplitude of the final and first PCM samples per channel. A jump above 0.08 suggests possible click risk. This is insufficient to prove a click or a clean loop, especially if WAV loop metadata defines nontrivial loop points. Godot's documented AudioStreamWAV loop settings and import points must be checked independently: https://docs.godotengine.org/en/stable/classes/class_audiostreamwav.html

**Human review**: the generated review-template.json uses 1..5 integer fields scene_fit, motif_recognizability, loop_naturalness, mix_balance, plus notes per destination. Completed input requires a non-empty reviewer and valid ratings. Such review is a **self-reported, unverified human claim**, never an independent objective assessment. The system does not generate or fabricate ratings.

## Artifacts and safety

- evaluation.json: hashes, planned roles/scenes, loop-seam metrics, MIDI motif overlap candidates, flags, human-review provenance and **promotion_gate=HOLD**.
- review-queue.json: listening prompts for every music role.
- review-template.json: blank fields to be completed by an actual listener.

No writing to Godot assets or scenes, internet requests, credential access, cloud inference or automatic promotion. Invalid file paths, source hash mismatches, malformed MIDI, unsafe reviews, and output under a Godot project are rejected.

## Still needed

CI synthetic MIDI and WAV prove only algorithm behavior. For actual production promotion: genuine AMIX-exported media, provenance/license review, actual in-game sound scene wiring, measured shared-clock alignment, real non-Dummy audio capture, multi-platform review, and listening feedback are required. M0.5 remains incubation and never auto-promotes.
