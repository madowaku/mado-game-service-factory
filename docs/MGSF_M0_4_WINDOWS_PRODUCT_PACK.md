# MGSF-M0.4 Windows Product Pack

Status: **BUILDING**

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

## M0.4 completion criteria

- Windows x64 EXE builds in CI.
- EXE `self-check` succeeds from the assembled product folder.
- EXE bundled `demo` succeeds.
- EXE can analyze the sample capture.
- ZIP contains docs, sample, report, and release manifest.
- Release manifest contains SHA-256 for every packaged file.
- Windows CI uploads the versioned ZIP as an artifact.
