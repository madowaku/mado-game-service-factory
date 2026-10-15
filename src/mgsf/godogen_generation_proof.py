"""MGSF M0.9.2: opt-in generated-game replay and cross-run autonomy evidence gate."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
import json
import re

from .godogen_adapter import _run_step, _sha, RESULT_FIELDS
from .godogen_frame_proof import verify_frame_proof
from .godogen_source_fingerprint import fingerprint_project, SourceFingerprintError
from .godogen_state_verification import (
    _write, load_contract, verify_state, StateVerificationError,
)


@dataclass(frozen=True)
class AutonomyVerdict:
    root: Path
    status: str
    checks_passed: int
    checks_total: int


def _manifest_and_source(project: Path) -> tuple[dict, dict]:
    if (project / ".mgsf-gyro-dogfood").exists():
        raise StateVerificationError("hand-authored GYRO fixture cannot claim autonomous generation")
    manifest_path = project / ".mgsf/godogen-intake.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise StateVerificationError("missing pinned Godogen source manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sha = manifest.get("upstream_sha", "")
    if (manifest.get("upstream") != "htdt/godogen"
        or manifest.get("engine") != "godot"
        or not isinstance(sha, str)
        or not re.fullmatch("[0-9a-fA-F]{40}", sha)):
        raise StateVerificationError("unverified Godogen source identity")
    staged = manifest.get("staged_files", {})
    required = ("AGENTS.md", "godot.md", ".agents/skills/asset-gen/SKILL.md")
    if not isinstance(staged, dict) or set(staged) != set(required):
        raise StateVerificationError("incomplete staged source hashes")
    for name in required:
        path = project / name
        if not path.is_file() or path.is_symlink() or _sha(path) != staged[name]:
            raise StateVerificationError("staged Godogen source changed")
    try:
        generated = fingerprint_project(project)
    except SourceFingerprintError as exc:
        raise StateVerificationError(str(exc)) from exc
    return manifest, generated


def capture_generated_game(
    project: str | Path, mission_path: str | Path, output_root: str | Path, *,
    godot: str, dotnet: str = "dotnet", ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe", xvfb: bool = True,
) -> Path:
    """Only user-opted-in staged Godogen dirs; game code is still untrusted."""
    project = Path(project).resolve()
    _manifest, generated = _manifest_and_source(project)
    mission = load_contract(mission_path)
    if "frame_probe" not in mission:
        raise StateVerificationError("generated capture requires a frame_probe mission")
    run_id = "gen-" + uuid4().hex
    # The Codex construction loop may already own screenshots/proof.mp4.
    # Never overwrite its movie: capture into a NEW per-run directory.
    capture_base = project / ".mgsf" / "generated-captures"
    if capture_base.is_symlink():
        raise StateVerificationError("generated capture directory cannot be a symlink")
    capture_dir = capture_base / run_id
    capture_dir.mkdir(parents=True, exist_ok=False)
    frames = capture_dir / "frames"
    frames.mkdir()
    trace = capture_dir / "state-trace.json"
    video = capture_dir / "proof.mp4"
    trace_rel = trace.relative_to(project).as_posix()
    video_rel = video.relative_to(project).as_posix()
    checks: dict = {}
    for name, args, timeout in (
        ("dotnet_build", [dotnet, "build", "--nologo"], 240),
        ("godot_import", [godot, "--headless", "--path", str(project), "--import"], 120),
    ):
        checks[name] = _run_step(args, project, timeout)
        if checks[name]["returncode"] != 0:
            _write(Path(output_root) / "failure-evidence" / (name + ".json"), checks[name])
            raise StateVerificationError(f"{name} failed; see failure-evidence")
    command = [godot, "--path", str(project), "--write-movie",
               str(frames / "frame.png"), "--fixed-fps", "30", "--quit-after", "450",
               "--", "--mgsf-trace", str(trace), "--mgsf-run-id", run_id,
               "--mgsf-mission-id", mission["mission_id"]]
    if xvfb:
        command = ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24", *command]
    checks["godot_capture"] = _run_step(command, project, 240)
    if checks["godot_capture"]["returncode"] or not trace.is_file():
        _write(Path(output_root) / "failure-evidence/godot_capture.json", checks["godot_capture"])
        raise StateVerificationError("generated game did not emit real engine state trace")
    if len(list(frames.glob("frame*.png"))) < 400:
        raise StateVerificationError("generated game did not render enough movie frames")
    checks["ffmpeg_encode"] = _run_step(
        [ffmpeg, "-y", "-loglevel", "error", "-framerate", "30",
         "-i", str(frames / "frame%08d.png"),
         "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(video)], project, 180)
    if checks["ffmpeg_encode"]["returncode"] != 0 or not video.is_file():
        raise StateVerificationError("generated game video encode failed")
    if fingerprint_project(project)["digest"] != generated["digest"]:
        raise StateVerificationError("game sources changed while capturing gameplay")
    runner = {
        "runner": "mgsf-godot-runtime", "run_id": run_id, "returncode": 0,
        "source": "staged-godogen-candidate", "generated_source": generated,
        "engine_checks": checks, "trace_sha256": _sha(trace), "video_sha256": _sha(video),
    }
    state = verify_state(
        project, mission_path, trace_path=trace_rel,
        video_path=video_rel, runner_record=runner,
        output_root=output_root, ffprobe=ffprobe,
    )
    _write(state.root / "runner.json", runner)
    frame = verify_frame_proof(
        project, mission_path, trace_path=trace_rel,
        video_path=video_rel,
        state_evidence_path=state.root / "state-evaluation.json",
        output_root=output_root, ffmpeg=ffmpeg, ffprobe=ffprobe,
    )
    return frame.root / "frame-proof.json"


def _json_file(path: str | Path) -> dict:
    path = Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 3_000_000:
        raise StateVerificationError("missing, symlinked, or oversized evidence file")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise StateVerificationError("evidence JSON must be object")
    return data


def verify_autonomous_generation(
    project: str | Path, mission_path: str | Path, *,
    frame_proof: str | Path, state_evidence: str | Path,
    godogen_evaluation: str | Path, codex_runner: str | Path,
    output_root: str | Path, fixture: bool = False,
) -> AutonomyVerdict:
    project = Path(project).resolve()
    mission = load_contract(mission_path)
    if "frame_probe" not in mission:
        raise StateVerificationError("autonomy gate requires state and frame contract")
    frame = _json_file(frame_proof)
    state = _json_file(state_evidence)
    generation = _json_file(godogen_evaluation)
    runner_path = Path(codex_runner).resolve()
    runner = _json_file(runner_path)
    # The runner directory is created by MGSF's Codex exec, not supplied via self-report.
    logs = runner_path.parent
    def runner_file(name: str) -> Path:
        path = logs / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 20_000_000:
            raise StateVerificationError("missing or unsafe Codex runner companion")
        return path
    checks: dict[str, bool] = {}
    try:
        intake, source = _manifest_and_source(project)
    except StateVerificationError:
        intake = {}
        source = {}
    checks["pinned_godogen_intake"] = bool(intake)
    checks["generated_project_sources"] = bool(source.get("digest"))
    checks["codex_runner_recorded"] = bool(
        runner.get("runner") == "codex-exec"
        and runner.get("returncode") == 0
        and runner.get("cwd") == str(project)
        and isinstance(runner.get("command"), list)
        and len(runner["command"]) > 3
        and runner["command"][1] == "exec"
        and "--output-last-message" in runner["command"]
        and runner["command"][-1] == "-"
        and isinstance(runner.get("generated_source"), dict)
        and runner["generated_source"].get("digest") == source.get("digest")
    )
    try:
        checks["codex_logs_hashed"] = (
            runner.get("stdout_sha256") == _sha(runner_file("stdout.txt"))
            and runner.get("stderr_sha256") == _sha(runner_file("stderr.txt"))
        )
        answer = _json_file(runner_file("answer.json"))
        checks["codex_agent_result"] = (
            answer.get("mission_id") == mission["mission_id"]
            and all(answer.get(k) is True for k in RESULT_FIELDS)
            and answer.get("runtime_errors") == []
            and isinstance(answer.get("proof_video"), str)
            and bool(answer["proof_video"])
        )
        prompt = runner_file("prompt.txt").read_text(encoding="utf-8")
        checks["codex_mission_prompt"] = (
            mission["mission_id"] in prompt and "Build a Godot 4 .NET/C# game" in prompt
            and "State-to-Frame contract" in prompt
        )
    except (StateVerificationError, UnicodeDecodeError):
        checks.update(codex_logs_hashed=False, codex_agent_result=False, codex_mission_prompt=False)
    checks["codex_engine_probes"] = bool(
        isinstance(runner.get("engine_checks"), dict) and all(
            isinstance(runner["engine_checks"].get(k), dict)
            and runner["engine_checks"][k].get("returncode") == 0
            for k in ("dotnet_build", "godot_import", "godot_launch"))
    )
    checks["recorded_generation_evaluation"] = bool(
        generation.get("status") == "PASS"
        and generation.get("service") == "godogen-adapter"
        and generation.get("evidence_class") == "recorded_godogen_codex_run"
        and generation.get("mission_id") == mission["mission_id"]
        and generation.get("upstream_sha") == intake.get("upstream_sha")
        and generation.get("runner") == runner
        and isinstance(generation.get("video"), list) and bool(generation["video"])
    )
    state_runner = state.get("runner") if isinstance(state.get("runner"), dict) else {}
    state_runner_source = state_runner.get("generated_source") if isinstance(state_runner.get("generated_source"), dict) else {}
    checks["state_runner_same_generated_sources"] = bool(
        state_runner.get("source") == "staged-godogen-candidate"
        and state_runner_source.get("digest") == source.get("digest")
        and state_runner.get("returncode") == 0
    )
    checks["independent_engine_state_pass"] = bool(
        state.get("service") == "godogen-gameplay-state-verification"
        and state.get("status") == "PASS"
        and state.get("runner_verified") is True
        and state.get("video_verified") is True
        and state.get("mission_id") == mission["mission_id"]
        and state.get("evidence_class") == "recorded_godot_engine_dogfood"
    )
    checks["decoded_frame_state_pass"] = bool(
        frame.get("service") == "godogen-state-to-frame-proof"
        and frame.get("status") == "PASS"
        and frame.get("evidence_class") == "recorded_gameplay_frame_probe"
        and frame.get("mission_id") == mission["mission_id"]
        and frame.get("run_id") == state.get("run_id")
        and frame.get("source_state_evaluation_sha256") == _sha(Path(state_evidence))
        and frame.get("source_trace_sha256") == state.get("state_trace", {}).get("sha256")
        and frame.get("source_video_sha256") == state.get("video", {}).get("sha256")
        and len(frame.get("checks", [])) >= 3
        and all(isinstance(c, dict) and c.get("pass") is True for c in frame["checks"])
    )
    if fixture or not checks["codex_runner_recorded"] or not checks["pinned_godogen_intake"]:
        status = "HOLD"
    elif all(checks.values()):
        status = "PASS"
    else:
        status = "ITERATE"
    run_id = frame.get("run_id") if isinstance(frame.get("run_id"), str) else "unverified"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", run_id):
        raise StateVerificationError("unsafe evidence run id")
    root = Path(output_root) / mission["mission_id"] / run_id
    _write(root / "autonomy-evaluation.json", {
        "schema_version": 1, "service": "godogen-autonomous-generation-proof",
        "mission_id": mission["mission_id"], "run_id": run_id,
        "status": status, "evidence_class": "deterministic_generation_fixture" if fixture else "local_codex_godogen_cross_run",
        "upstream_sha": intake.get("upstream_sha"), "generated_source": source,
        "checks": checks, "passed": sum(checks.values()), "total": len(checks),
        "sources": {
            "codex_runner_sha256": _sha(runner_path),
            "godogen_evaluation_sha256": _sha(Path(godogen_evaluation)),
            "state_evaluation_sha256": _sha(Path(state_evidence)),
            "frame_proof_sha256": _sha(Path(frame_proof)),
        },
        "provenance_note": (
            "Local, reproducible chain-of-custody for a Codex/Godogen run; "
            "hashes and files are not cryptographic remote attestation. "
            "No release, license, human playtest or production approval."
        ),
    })
    return AutonomyVerdict(root, status, sum(checks.values()), len(checks))
