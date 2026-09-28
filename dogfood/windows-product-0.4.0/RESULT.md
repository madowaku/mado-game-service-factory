# Windows Product Pack 0.4.0 Result

Status: **PASS**

## Build

Workflow: `windows-product`

Run:

`36493989574`

Job:

`109169128163`

Platform:

`windows-latest`

Product:

`MADO Playtest Evidence 0.4.0`

## Verification

```text
15 passed
mado-playtest 0.4.0
demo findings=1 status=PASS
sample analyze findings=1 status=PASS
```

The packaged executable was run from inside the assembled product folder.

Verified commands:

```text
mado-playtest.exe --version
mado-playtest.exe self-check
mado-playtest.exe demo
mado-playtest.exe analyze examples\sample-capture
```

## Product ZIP

```text
MADO-Playtest-Evidence-0.4.0-win-x64.zip
bytes: 8,141,141
sha256: 690921e45c71308e6f4442fb10e411775349b7b5a96d12ba45e0cc259bdd553b
packaged files: 14
```

GitHub Actions artifact:

```text
artifact id: 11001819146
name: MADO-Playtest-Evidence-0.4.0-win-x64
artifact bytes: 8,143,104
expires: 2026-10-12
```

## Package contents

The product pack contains:

- single-file Windows x64 executable
- quickstart README
- privacy statement
- preview product license
- third-party notices
- support instructions
- release notes
- offline sample capture
- generated sample report
- release manifest containing per-file SHA-256 hashes

## Interpretation

This proves a portable Python-free Windows product preview can be built and executed by a clean GitHub Windows runner.

It does not yet prove non-technical first-run usability or paid-market readiness. External tester evidence remains valuable before a public paid release.
