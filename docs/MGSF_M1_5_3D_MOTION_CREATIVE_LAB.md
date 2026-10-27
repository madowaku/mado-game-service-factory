# MGSF-M1.5 (proposed): 3D & Motion Creative Lab

**Status:** incubation / isolated experiment. This is not a live image-to-3D generator or a visual-quality oracle.

## Boundary and reuse

- **MGSF** owns execution contracts, reproducibility, evidence and promotion decisions.
- **MAF** (madowaku/mado-asset-foundry) already owns source-license intake, curation, asset QA, packaging, and Godot asset dogfood. Never duplicate it.
- Existing Godot workflows continue unchanged. The lab has no network access and never installs, clones, downloads or executes creative code.
- No paid APIs or model weights are needed to test this contract.

## Upstream candidates (research only, no vendored code)

| Source | Opportunity | Boundary |
| --- | --- | --- |
| [img2threejs](https://github.com/img2threejs/img2threejs) | Reference-image-to-procedural Three.js | Requires a separately exported GLB; generated JS is not directly imported by this lab |
| [video-shotcraft](https://github.com/Vincentwei1021/video-shotcraft) | Code-based promo shots | MP4/Remotion rendering and license review are not implemented here |
| [mg-styles-15](https://github.com/Vincentwei1021/mg-styles-15) | Motion style samples and prompts | Study metadata; no automatic reuse |
| [dioramas](https://github.com/blendi-remade/dioramas) | Camera, light and interactive 3D studies | Separate sandbox |
| Motion2MixamoRig, dsh-blender-plugin, lemo-opuscar | Later experiments | No automatic adapter promotion |

Public source code does not automatically authorize redistribution of assets or rigs. Remotion, motion models, third-party art and bundled dependencies may have separate terms.

## Working command

    mgsf creative-qa <run-directory> --output-root evidence

One run directory must contain:
- run.json with explicit source assertion and license/review fields
- reference PNG and a GLB binary glTF 2.0 with mesh, nodes, POSITION accessor, JSON and BIN chunks
- 2 to 240 consistent-dimension, non-identical PNG render frames
- optional procedural .js or .ts source (only hashed, never executed)

The scanner rejects noncanonical or absolute paths, symlinks, duplicate frame paths, empty/oversize files (limit 50 MiB each), corrupt GLB structure, invalid PNG headers and evidence overwrites. It records SHA-256 hashes, byte sizes, dimensions, frames and a GLB summary, in an evidence file outside the source tree.

**Structural PASS is not an artistic judgment or release approval.** Even with local-render assertions, promotion is **HOLD** pending real Godot GLB import, actual rendered screenshots, human fidelity assessment and source/dependency license review. PNG checking is header-only; GLB checking is structural, not a full validator. Synthetic frames must not be described as direct gameplay captures.

## Reproducible, dependency-free fixture

After installing the project via python -m pip install -e ".[dev]":

    python scripts/make_creative_lab_fixture.py /tmp/mgsf-creative-fixture
    mgsf creative-qa /tmp/mgsf-creative-fixture --output-root /tmp/mgsf-creative-evidence
    pytest -q tests/test_creative_lab.py

Fixture output is a synthetic triangle GLB, a reference PNG, and two distinct PNG frames. Expected result: **structural PASS / promotion HOLD**. It does NOT run img2threejs, video-shotcraft, Blender or Godot.

## run.json contract example

    {
      "schema_version": 1,
      "run_id": "object-probe-001",
      "reference_image": "reference.png",
      "scene": "scene.glb",
      "source_code": "procedural-scene.js",
      "frames": ["frames/000.png", "frames/001.png"],
      "source": {
        "evidence_class": "operator_supplied_local_render",
        "generator": "local-threejs-export"
      },
      "rights": {
        "license": "unknown",
        "reviewed": false
      }
    }

All artifact paths are relative. Use a new run_id/output root for each experiment to avoid overwrites. The source.evidence_class value records the operator's assertion, not independently verified engine evidence.

## Next experiments and quality gates

1. **3D probe:** Rebuild one owned/licensed reference object with img2threejs, export GLB by an explicit local step, render screenshots and verify Godot imports and displays the result. Preserve renderer version, source SHA and media hashes.
2. **Motion probe:** Use consented owned gameplay material to build a 15-second teaser with video-shotcraft/Remotion; extract rendered frames via an explicitly approved local step. Do not present reconstructed shots as gameplay captures.
3. **Style intelligence:** Maintain a style recommendation dictionary informed by mg-styles-15/dioramas and compare outputs with a human rubric for style alignment, legibility, motion clarity, accessibility, composition and performance.
4. **MAF bridge:** After approval, hand assets to the existing MAF license/curation/packaging/Godot checks. No duplicate asset-publishing pipeline.

Promotion requires actual code runner and pinned-commit evidence, real engine browser or Blender screenshots, real Godot import verification, independent licensing review, and human visual acceptance. Until then the lab stays in incubation with a HOLD gate.
