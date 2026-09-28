# Vertical Slice C6 Direct Capture Dogfood

Status: **PASS**

## Source

- Repository: `madowaku/vertical-slice`
- Capture SHA: `f0514229d7f2036ec25646d09e3647c8d870dadb`
- Engine: Godot 4.7.2
- Scenario: C6 one-cell-early near miss

## MGSF execution

- CI run: `36488219481`
- Job: `109150207262`
- Adapter result: `PASS`
- Findings: 1
- Factory tests: 12 passed
- Evidence artifact: `11000425066`

## Direct media

### before-swing.png

- PNG
- 1280 x 720
- RGBA
- SHA-256: `ac5c0ec22875fe6222021fc82d420abd3195a518904cbd39febd8ff953d7ddcd`

### reveal.png

- PNG
- 1280 x 720
- RGBA
- SHA-256: `126240e5e70057d17be6322137d3c662c4361a993ce39b2cf4157a2322a98d51`

## Promotion signals

- `recorded_gameplay_capture = true`
- `direct_media_reaches_finding = true`
- capture eval PASS
- capture-to-playtest eval PASS
- Godot adapter eval PASS

This evidence satisfies the M0.3 promotion gate for `gameplay-capture`.
