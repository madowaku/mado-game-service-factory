# MGSF Pixel Volume Studio M0.1

Status: **incubation**. This is a sprite-stacking asset pipeline and Godot demo, not a production renderer endorsement.

## Scope

- Input: reproducible JSON containing colored boxes and ellipsoids (voxel primitives).
- Output: transparent horizontal sprite sheet PNG + deterministic manifest with SHA-256 and explicit provenance.
- Renderer: Godot 4 Node2D stacking the leftmost (bottom) slice first, rotating all layers, compressing Y, then lifting each successive slice.
- Fully local and offline. Python runtime standard library only. No paid API.
- Out of scope: four-orthographic-view reconstruction, Blender/MagicaVoxel import, animation caching, live performance metrics, automatically installing external addons.

## Try it

From the repository root after installing with pip install -e .:

    python -m mgsf.pixel_volume fixtures/pixel-volume/toy-car.json examples/godot-pixel-volume/generated
    python -m mgsf.pixel_volume fixtures/pixel-volume/tree.json examples/godot-pixel-volume/generated
    python -m mgsf.pixel_volume fixtures/pixel-volume/paper-house.json examples/godot-pixel-volume/generated

Open examples/godot-pixel-volume/project.godot in Godot 4.x and run the scene. The sprite stacks should spin independently. To use in another Godot 4 project, copy stack_sprite.gd, assign an imported Texture2D, and set layers to the manifest's slices value. Sort the **whole stack** at the contact point, not each layer. Round world positions at pixel resolution and use nearest filtering.

## Evidence and acceptance

| Check | Result expected for M0.1 |
|---|---|
| Input validation and bounds | Invalid JSON shapes fail |
| Reproducibility | Same fixture produces byte-identical PNG |
| Sprite ordering | Left slice is ground; right slice is top |
| Provenance | Input SHA, PNG SHA, fixture source class |
| Actual Godot screenshot / renderer test | **Not yet verified** until externally run and captured |
| Live game dogfood | **Not done** |
| Promotion gate | **HOLD** until real-engine evidence exists |

Next M0.2: accept a sprite sheet from 4 orthographic views or Blender/MagicaVoxel; evaluate visual fidelity at 0°, 30°, 90° and 180°; benchmark 10, 100, and 500 objects; capture the actual Godot frame via the MGSF gameplay-capture adapter. Alternative third-party renderers: [Shader-Stacker](https://github.com/x3cca/Shader-Stacker) (MPL-2.0, different **vertical** sheet format) and [SpriteStack2D](https://github.com/VitSoonYoung/SpriteStack2D) (MIT, 2x2 orthographic source); pin versions, re-evaluate compatibility and licenses before adoption.

## Sources

- Technique, horizontal slice layout, Godot baseline: https://www.spritecook.ai/blog/sprite-stacking-pixel-art
- Godot alternative (vertical sheets): https://github.com/x3cca/Shader-Stacker
- 4-view alternative: https://github.com/VitSoonYoung/SpriteStack2D

This implementation contains original generator and glue code; it does not copy third-party addon code.
