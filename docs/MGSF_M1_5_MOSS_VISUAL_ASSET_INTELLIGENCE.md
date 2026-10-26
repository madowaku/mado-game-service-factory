# MGSF-M1.5 MOSS Visual Asset Intelligence

Status: incubation. Offline handoff and candidate QA only.

## Scope

- Convert editable Layout drafts to MOSS-Image-ready positive prompts with exact Japanese copy, 16-pixel-aligned canvas and official abs/xyxy to abs_centralized/yxyx conversion.
- Preserve original draft, compiled prompt, model declaration and SHA-256 hashes.
- Optionally inspect externally generated PNG structure/CRC, canvas size, candidate hash and explicit human review.
- Never download model weights, call API endpoints, launch ComfyUI, publish assets, change a Godot project or claim a real model generation.

## Commands

    mgsf moss-visual-plan fixtures/moss-visual/title-screen.json
    mgsf moss-visual-plan fixtures/moss-visual/store-capsule.json
    mgsf moss-visual-plan fixtures/moss-visual/tutorial-panel.json
    mgsf moss-visual-eval evidence/moss-visual/store-capsule

Use a new output root per run. Repeated plan calls will not overwrite existing evidence. The three fixtures exercise title-screen art, store capsule and manga-like tutorial with literal Japanese strings.

Plan outputs are: draft.json, prompt.txt, manifest.json. Paste the contents of prompt.txt into the official MOSS-Image Gradio positive prompt or compatible local ComfyUI workflow. Choose the model declared in manifest and EXACTLY the canvas dimensions in manifest. No image is rendered by MGSF.

Once a candidate PNG exists, check it:

    mgsf moss-visual-eval evidence/moss-visual/store-capsule --image path/to/candidate.png
    mgsf moss-visual-eval evidence/moss-visual/store-capsule --image path/to/candidate.png --review path/to/review.json

A review.json has this structure (replace hash placeholders with actual SHA-256):

    {
      "image_sha256": "<candidate PNG SHA-256>",
      "prompt_sha256": "<manifest prompt_sha256>",
      "observed_text": ["歯車の庭", "ひらめきで\n世界をまわそう"],
      "composition_approved": true,
      "style_consistent": true,
      "reviewer": "manual-qa"
    }

Observed text must be transcribed from the rendered image, not copied blindly from manifest. The reviewer checks text legibility, Japanese spelling, composition, style and suitability for the intended placement. Reported reviewer identity is unverified self-report, not cryptographic proof.

Gate semantics:
- HOLD: no PNG, no review, incorrect observed text or unapproved visual conditions.
- FAIL: wrong dimensions, malformed/corrupted PNG or inconsistent review hashes.
- PASS: a locally supplied candidate has passed file checks and has explicit hash-bound human approval. This is candidate review only, NOT verified MOSS inference, distribution rights, a game integration or active service promotion.

PNG parsing checks chunk order/CRC and dimensions, not pixel decoding, typography or OCR. A genuine live dogfood and external QA are required before promoting lifecycle status.

## Upstream pin and licenses

Official: https://github.com/OpenMOSS/MOSS-Image

The unmodified official compile_prompt.py from skills/moss-image-prompt-enhancer/scripts is vendored under src/mgsf/vendor/moss_compile_prompt.py. Source blob SHA, source URL and retrieval date are in third_party/OpenMOSS-MOSS-Image-NOTICE.md, with its Apache-2.0 license beside it. There are no vendored weights, engine libraries or inference dependencies.

The official prompt-enhancer Skill additionally contains creative guidance; the tool incorporated here is only its deterministic coordinate compiler. Check any installed models and third-party LoRAs individually for licenses and operating requirements.

## Integration boundary

MADO Asset Foundry already has image-provider contracts, candidate curation, QA and game-asset packaging. This MGSF service does not pretend to be a MAF provider, and MAF currently has no confirmed MOSS inference bridge from this PR. Next: an opt-in local ComfyUI/MOSS provider in MAF, sandboxed preflight and output verification, visual/OCR comparisons, then real-project dogfood on all three sample types. No automatic game publishing.
