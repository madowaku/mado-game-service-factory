# itch.io Productization Gate

Status: **Windows preview proven; external tester and final review gates remain**

## Product shape

MADO Game Service Factory is being packaged as a game-development Tool rather than as a hosted SaaS.

Customer-facing product:

**MADO Playtest Evidence**

Promise:

> Record or import a playtest, preserve the evidence, and get a report tied to exact frames.

Avoid selling the internal Factory architecture as the product.

## Technical/product gates completed

- [x] direct `recorded_gameplay_capture` from a running game passes
- [x] at least one Godot project is captured end-to-end
- [x] capture-to-report finding includes direct media hashes
- [x] portable Windows x64 package exists
- [x] Python is not required on the target Windows machine
- [x] first-run commands are documented
- [x] offline sample session is included
- [x] generated sample report is included
- [x] privacy behavior is documented
- [x] preview license model is explicit
- [x] versioned build recipe exists
- [x] release manifest hashes every packaged file
- [x] support/contact route is documented

## Paid public-release gates still open

- [ ] external tester completes unzip -> self-check -> demo without live guidance
- [ ] SmartScreen/antivirus behavior is observed on a normal Windows machine
- [ ] final publisher/legal review of `PRODUCT_LICENSE.txt`
- [ ] final third-party license review and any required full notices
- [ ] Godot-project onboarding is understandable without repository-specific knowledge
- [ ] AI disclosure fields are reviewed against itch.io's current publishing UI
- [ ] pricing and refund/support expectations are decided

## Windows proof

Workflow run:

`36493989574`

Job:

`109169128163`

Product:

`MADO-Playtest-Evidence-0.4.0-win-x64.zip`

Proof:

```text
15 tests passed
mado-playtest 0.4.0
bundled demo: findings=1 PASS
sample analyze: findings=1 PASS
14 packaged files
ZIP bytes: 8,141,141
ZIP SHA-256:
690921e45c71308e6f4442fb10e411775349b7b5a96d12ba45e0cc259bdd553b
```

Artifact:

`11001819146`

## Distribution shape

```text
MADO-Playtest-Evidence-0.4.0-win-x64/
├── mado-playtest.exe
├── README.txt
├── PRIVACY.txt
├── PRODUCT_LICENSE.txt
├── THIRD_PARTY_NOTICES.txt
├── SUPPORT.txt
├── RELEASE_NOTES.txt
├── RELEASE-MANIFEST.json
└── examples/
    ├── sample-capture/
    └── sample-report/
```

## Pricing experiment

Treat pricing as an experiment, not a permanent commitment.

Suggested sequence:

1. a few private/external preview testers
2. free or pay-what-you-want public preview if onboarding is still rough
3. paid early access around the low-teens USD range once first-run friction is understood
4. raise price only after packaging polish and broader project/engine proof

## itch.io metadata draft

Classification: Tool

Potential tags:

- game-development
- Game Design
- Godot
- Testing
- Productivity

Only use platform flags for executables actually tested on those platforms.

## AI disclosure

The project is developed with generative-AI coding assistance.

Before publishing, review itch.io's current AI disclosure options and accurately disclose generated code and any generated text/graphics included in the distributed product.

## Product principle

Sell the outcome, not the architecture.

Preferred headline:

> Record a playtest. Get a report that points back to the exact gameplay evidence.
