# MGSF-UNITY-M0.7: Unity CLI / Pipeline Agent Harness

## Scope
A separate Unity incubation track; the existing MGSF-M0.7 identifier belongs to EdenSpark's Autonomous Playtest Loop. Godot capture and EdenSpark MCP are not changed.

The harness runs on the **local developer machine** with Unity 6+, Unity CLI and com.unity.pipeline. It does not install Editors, run C# eval, edit scenes, trigger builds, configure MCP, or publish projects. This keeps the initial CLI bridge auditable and reversible.

1. Verify a Unity project by ProjectSettings/ProjectVersion.txt and Assets/.
2. Probe unity version and unity status in machine-readable JSON.
3. Fail closed unless exactly one ready Editor reports the requested project path.
4. Inspect the Pipeline command manifest using unity list.
5. Optionally run Unity EditMode tests with unity test, preserving the actual NUnit XML.
6. Preserve stdout and stderr text plus SHA-256 and return code for every step.

The optional test run is explicitly authorized by --run-tests. A real PASS requires a ready project-matched Editor, successful JSON command manifest, zero CLI test errors, and a nonempty NUnit report with zero failures. A read-only probe always HOLDs; failed tests ITERATE. All fixture runs HOLD even with --run-tests.

## Usage

Install/update Unity CLI and Pipeline as documented by Unity (the API is experimental). Open your Unity project in a Unity Editor with com.unity.pipeline installed.

~~~powershell
unity --version
unity pipeline install
unity status --format json
mgsf unity-harness C:\Dev\MyUnityGame
mgsf unity-harness C:\Dev\MyUnityGame --run-tests --timeout-seconds 1800
~~~

Test the contract in any Python environment, without installing Unity:

~~~bash
mgsf unity-harness fixtures/unity/fixture-project --fixture fixtures/unity/fixture-probe.json --run-tests --output-root evidence/unity-fixtures
pytest -q tests/test_unity_cli_harness.py
~~~

CLI exit codes: PASS = 0, HOLD = 0 (with a clearly labeled evidence gate), ITERATE = 1. If the project path itself is invalid, command validation raises an error. Inspect <output-root>/<project>-<run-id>/evaluation.json for the authoritative result and evidence class.

## Safety and promotion limits
- Never call a deterministic fixture a live Unity Editor invocation.
- PASS proves CLI/Pipeline connection plus EditMode test execution, **not** gameplay playthrough, asset export, screenshot evidence, or agent-authored scene edits.
- C# eval and arbitrary editor commands are outside this milestone. A later opt-in sandbox/policy gateway can grant them.
- No automatic install, no silent --allow-install, no cloud API credentials, and no automatic publishing.
- Do not assume the CLI's stdout is evidence merely because it has exit code zero: only parseable non-error JSON envelopes are accepted.
- Project identity must match the Editor status; multiple ready Editor entries cause HOLD.
- External Unity operations run locally, not in repository CI. CI checks the deterministic fixture contract and Python tests only.

Sources:
- https://docs.unity.com/en-us/unity-cli
- https://docs.unity.com/en-us/unity-cli/unity-cli-reference
- https://unity.com/resources/a-beginners-guide-to-unity-cli-and-the-pipeline-package
- https://github.com/Unity-Technologies/unity-agent-plugin
