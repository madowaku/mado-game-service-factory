MADO PLAYTEST EVIDENCE 0.4.0
Windows x64 Product Preview

WHAT IT DOES

MADO Playtest Evidence turns gameplay evidence into a report whose findings
point back to the exact media used as evidence.

The current product preview supports:
- packaged capture analysis
- bundled sample analysis
- Godot capture scenes that emit the MADO capture contract
- SHA-256 media indexing
- evidence-backed playtest reports

QUICK START

1. Extract the ZIP to a normal writable folder.

2. Open PowerShell or Command Prompt in that folder.

3. Check the package:

   mado-playtest.exe self-check

4. Run the bundled sample:

   mado-playtest.exe demo

   Output is written to:
   mado-evidence\

5. Analyze your own MADO capture directory:

   mado-playtest.exe analyze C:\path\to\capture

GODOT DIRECT CAPTURE

A Godot project needs a compatible MADO capture scene.

If Godot is on PATH or installed in a common location:

   mado-playtest.exe godot C:\path\to\godot-project

Or specify it:

   mado-playtest.exe godot C:\path\to\godot-project ^
     --godot C:\path\to\Godot_v4.7.2-stable_win64.exe

The first proven adapter target is the MADO vertical-slice C6 capture scene.

FILES

mado-playtest.exe
  Product executable.

examples\sample-capture\
  Offline sample input. This is reconstructed evidence, not a direct screenshot.

examples\sample-report\
  Example report generated from the bundled sample.

PRIVACY.txt
  What the product reads/writes and its network behavior.

PRODUCT_LICENSE.txt
  Preview product license. Review before a paid commercial release.

THIRD_PARTY_NOTICES.txt
  Third-party runtime/build notices.

RELEASE-MANIFEST.json
  File hashes and build provenance for this package.

SUPPORT.txt
  Support and issue-reporting information.

VERIFICATION

The 0.4.0 Windows pack has been built and smoke-tested on a clean GitHub
Windows runner.

Verified:
- mado-playtest.exe --version
- self-check
- bundled demo
- sample analyze
- 15 automated tests

The distributed executable is unsigned in this preview. Windows SmartScreen or
antivirus reputation warnings may appear on some machines. External tester
evidence is the next product milestone.

LIMITS OF THIS PREVIEW


- No GUI yet.
- No automatic instrumentation of arbitrary Godot games.
- Direct Godot capture requires a compatible capture scene.
- Confusion/surprise values remain modeled values unless human telemetry is supplied.
- The tool does not claim reconstructed media is direct gameplay capture.
