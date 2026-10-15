"""MGSF M0.9.3: one-command, explicitly authorized real Codex/Godogen qualification.

There is NO unattended or credentialed GitHub Actions execution. The default
mode is a harmless preflight, and the live path requires two explicit flags.
Only observed evidence with independent state/frame replay can yield PASS.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Any
import json
import re
import shutil

from .godogen_adapter import intake_godogen, load_mission, run_godogen_loop, _sha
from .godogen_frame_proof import load_frame_probe
from .godogen_generation_proof import capture_generated_game, verify_autonomous_generation
from .godogen_state_verification import load_contract, StateVerificationError


class QualificationError(ValueError):
    """Preflight failed before any external command or mutation."""


@dataclass(frozen=True)
class Qualification:
    status: str
    stage: str
    reason: str
    report: Path | None


def _write(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def preflight(
    source: str | Path, target: str | Path, mission_path: str | Path, *,
    expected_sha: str, codex: str = "codex", godot: str = "godot",
    dotnet: str = "dotnet", ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
    xvfb: bool = True,
) -> dict[str, Any]:
    source, target = Path(source).resolve(), Path(target).resolve()
    if not re.fullmatch(r"[a-fA-F0-9]{40}", expected_sha):
        raise QualificationError("expected_sha must pin a full 40-character Git commit")
    # Preview invokes only local, bounded Git metadata queries. It never runs
    # upstream scripts, Codex, the game engine, or paid asset generation.
    source_plan = intake_godogen(source, target, expected_sha, dry_run=True)
    mission = load_mission(mission_path)
    load_contract(mission_path)
    load_frame_probe(mission)
    tools = {"codex": codex, "godot": godot, "dotnet": dotnet,
             "ffmpeg": ffmpeg, "ffprobe": ffprobe}
    if xvfb:
        tools["xvfb-run"] = "xvfb-run"
    availability = {name: bool(shutil.which(exe)) for name, exe in tools.items()}
    missing = sorted(name for name, ok in availability.items() if not ok)
    return {
        "schema_version": 1, "service": "godogen-real-codex-qualification",
        "mission_id": mission["mission_id"],
        "source": str(source), "target": str(target),
        "upstream_sha": source_plan["upstream_sha"],
        "intake_policy": source_plan["policy"],
        "tool_availability": availability, "missing_tools": missing,
        "max_iterations": mission["max_iterations"],
        "dry_run": True,
        "status": "READY" if not missing else "BLOCKED",
        "live_codex_execution": False,
        "live_godot_execution": False,
        "credential_check": "not_checked; Codex uses its own configured local login",
        "risk_note": (
            "Generated source is untrusted. Execute on an isolated, expendable "
            "machine with no secrets. Local SHA metadata is not signed remote attestation."
        ),
    }


def qualify(
    source: str | Path, target: str | Path, mission_path: str | Path, *,
    expected_sha: str, output_root: str | Path,
    execute: bool = False, accept_generated_code_risk: bool = False,
    codex: str = "codex", godot: str = "godot", dotnet: str = "dotnet",
    ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe", xvfb: bool = True,
    timeout_seconds: int = 1800,
) -> Qualification:
    plan = preflight(source, target, mission_path, expected_sha=expected_sha,
                     codex=codex, godot=godot, dotnet=dotnet,
                     ffmpeg=ffmpeg, ffprobe=ffprobe, xvfb=xvfb)
    if not execute:
        return Qualification(plan["status"], "preflight", json.dumps(plan, indent=2), None)
    if not accept_generated_code_risk:
        raise QualificationError("--execute requires --accept-generated-code-risk")
    if plan["missing_tools"]:
        raise QualificationError("missing required tools: " + ", ".join(plan["missing_tools"]))
    if not 1 <= timeout_seconds <= 7200:
        raise QualificationError("timeout_seconds must be between 1 and 7200")
    target = Path(target).resolve()
    source = Path(source).resolve()
    mission_path = Path(mission_path).resolve()
    output_root = Path(output_root).resolve()
    if output_root == source or output_root.is_relative_to(source):
        raise QualificationError("evidence must be written outside the Godogen checkout")
    if output_root == target or output_root.is_relative_to(target) or target.is_relative_to(output_root):
        raise QualificationError("output_root and generated project must be disjoint")
    run_id = "codex-" + uuid4().hex
    report_path = output_root / "qualifications" / plan["mission_id"] / run_id / "qualification.json"
    report: dict[str, Any] = {
        "schema_version": 1, "service": "godogen-real-codex-qualification",
        "run_id": run_id, "mission_id": plan["mission_id"],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "upstream_sha": plan["upstream_sha"],
        "target": str(target), "state": "HOLD", "stage": "intake",
        "reason": "qualification incomplete",
        "codex_stage_attempted": False, "real_codex_observed": False,
        "independent_game_replay_observed": False,
        "autonomous_generation_qualified": False,
        "artifacts": {},
        "provenance_note": (
            "Evidence reflects a local process, not independent AI authorship "
            "attestation, licensing, security audit, or release authorization."
        ),
    }
    def persist() -> None:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        _write(report_path, report)

    persist()
    try:
        staged = intake_godogen(source, target, expected_sha, dry_run=False)
        report["stage"] = "codex-generation"
        report["artifacts"]["intake_sha256"] = _sha(target / ".mgsf/godogen-intake.json")
        persist()

        report["codex_stage_attempted"] = True
        persist()
        generation = run_godogen_loop(
            target, mission_path, output_root / "generation",
            codex=codex, godot=godot, dotnet=dotnet,
            ffprobe=ffprobe, timeout_seconds=timeout_seconds,
        )
        generation_path = generation.root / "evaluation.json"
        runner_path = generation.root / "runner" / "runner.json"
        report["artifacts"]["generation_evaluation"] = str(generation_path)
        report["artifacts"]["generation_runner"] = str(runner_path)
        if runner_path.is_file():
            runner = json.loads(runner_path.read_text(encoding="utf-8"))
            report["real_codex_observed"] = (
                runner.get("runner") == "codex-exec"
                and runner.get("returncode") == 0
            )
        if generation.status != "PASS":
            report["state"] = "HOLD"
            report["reason"] = f"Codex generation contract did not pass: {generation.status}"
            report["stage"] = "codex-generation"
            persist()
            return Qualification(report["state"], report["stage"], report["reason"], report_path)

        report["stage"] = "independent-game-replay"
        persist()
        frame_path = capture_generated_game(
            target, mission_path, output_root / "generated-replay",
            godot=godot, dotnet=dotnet, ffmpeg=ffmpeg,
            ffprobe=ffprobe, xvfb=xvfb,
        )
        report["independent_game_replay_observed"] = True
        state_path = frame_path.parent / "state-evaluation.json"
        report["artifacts"]["frame_proof"] = str(frame_path)
        report["artifacts"]["state_evaluation"] = str(state_path)
        persist()

        report["stage"] = "autonomy-gate"
        verdict = verify_autonomous_generation(
            target, mission_path, frame_proof=frame_path,
            state_evidence=state_path, godogen_evaluation=generation_path,
            codex_runner=runner_path, output_root=output_root / "autonomy",
        )
        report["artifacts"]["autonomy_evaluation"] = str(verdict.root / "autonomy-evaluation.json")
        report["state"] = verdict.status
        report["reason"] = f"cross-run evidence: {verdict.checks_passed}/{verdict.checks_total} checks"
        report["autonomous_generation_qualified"] = verdict.status == "PASS"
        persist()
        return Qualification(report["state"], report["stage"], report["reason"], report_path)
    except Exception as exc:
        # Fail closed. No token values or raw Codex logs are copied here.
        report["state"] = "HOLD"
        report["reason"] = f"{type(exc).__name__} during {report['stage']}; inspect local runner evidence"
        report["failed_stage"] = report["stage"]
        persist()
        return Qualification(report["state"], report["stage"], report["reason"], report_path)
