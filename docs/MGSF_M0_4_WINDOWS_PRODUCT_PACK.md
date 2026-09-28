# MGSF-M0.4 Windows Product Pack

Status: **COMPLETE**

## Goal

Turn the active MGSF services into a portable Windows x64 preview that an external tester can unzip and run without installing Python.

## Product surface

Customer-facing executable:

`mado-playtest.exe`

Commands:

```text
mado-playtest.exe self-check
mado-playtest.exe demo
mado-playtest.exe analyze <capture-dir>
mado-playtest.exe godot <godot-project> [--godot <Godot.exe>]
```

The product CLI intentionally hides the internal Factory lifecycle commands.

## Package

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

## Build

The pack is built on `windows-latest` with the Python 3.12 line and pinned Python build dependencies. The exact Python patch version used by CI is recorded in `RELEASE-MANIFEST.json`.

PyInstaller creates a single-file executable.

The builder then:

1. copies the customer-facing documents;
2. copies the offline reconstructed sample;
3. generates a sample report;
4. hashes every distributed file;
5. writes `RELEASE-MANIFEST.json`;
6. creates a versioned ZIP.

The ZIP writer sorts paths and uses normalized ZIP timestamps so the packaging layer is deterministic. The frozen executable itself is tracked by SHA-256 in the release manifest.

## Privacy

Version 0.4.0 has no intentional product telemetry or cloud upload.

Gameplay media stays local unless the user separately chooses to share it.

## License state

A proprietary preview license is included.

It allows personal, educational, evaluation, and internal commercial game-development use while prohibiting redistribution/resale of the tool itself.

The license is explicitly marked for publisher review before the first paid public release.

## Windows proof

Workflow run:

`36493989574`

Job:

`109169128163`

Verification:

```text
15 passed
mado-playtest 0.4.0
demo findings=1 status=PASS
sample analyze findings=1 status=PASS
```

Product ZIP:

```text
MADO-Playtest-Evidence-0.4.0-win-x64.zip
8,141,141 bytes
sha256 690921e45c71308e6f4442fb10e411775349b7b5a96d12ba45e0cc259bdd553b
14 packaged files
```

Artifact:

`11001819146`

## M0.4 completion criteria

- [x] Windows x64 EXE builds in CI.
- [x] EXE `self-check` succeeds from the assembled product folder.
- [x] EXE bundled `demo` succeeds.
- [x] EXE can analyze the sample capture.
- [x] ZIP contains docs, sample, report, and release manifest.
- [x] Release manifest contains SHA-256 for every packaged file.
- [x] Windows CI uploads the versioned ZIP as an artifact.

## Next product gate

The highest-value evidence now comes from humans outside the development loop.

Recommended next milestone:

`MGSF-M0.5 External Tester Preview`

Focus:

- download/unzip friction
- first-run comprehension
- Windows SmartScreen/antivirus friction
- Godot discovery/setup friction
- report usefulness
- privacy/license comprehension
