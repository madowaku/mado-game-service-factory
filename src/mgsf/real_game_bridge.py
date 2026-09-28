from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .playtest_report import run_playtest_report

BRIDGE_ID = "real-game-bridge"
BRIDGE_VERSION = "0.2.0"


class RealGameBridgeError(ValueError):
    """Raised when recorded real-game evidence cannot be trusted enough to bridge."""


@dataclass(frozen=True)
class RealGameBridgeRun:
    root: Path
    mgel_root: Path
    bridge_eval_path: Path
    manifest_path: Path
    normalized_record_path: Path
    runtime_log_path: Path
    eval_status: str
    fixture_id: str
    session_id: str


@dataclass(frozen=True)
class RealGameDogfoodRun:
    bridge: RealGameBridgeRun
    report_root: Path
    dogfood_eval_path: Path
    status: str
    finding_count: int


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RealGameBridgeError(f"could not read valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise RealGameBridgeError("real-game record root must be an object")
    return payload


def load_real_game_record(path: str | Path) -> dict[str, Any]:
    record = _read_json(Path(path))
    if record.get("version") != 1:
        raise RealGameBridgeError("real-game record version must be 1")

    source = record.get("source")
    session = record.get("session")
    scenario = record.get("scenario")
    if not all(isinstance(item, dict) for item in (source, session, scenario)):
        raise RealGameBridgeError("source, session, and scenario must be objects")

    required_source = (
        "repository",
        "source_head_sha",
        "tested_merge_sha",
        "workflow_run_id",
        "workflow_job_id",
        "engine",
        "test_suite",
        "test_file",
        "evidence_class",
        "required_log_markers",
    )
    for key in required_source:
        if key not in source:
            raise RealGameBridgeError(f"source.{key} is required")

    if source["evidence_class"] != "real_project_headless_test":
        raise RealGameBridgeError(
            "M0.2 only accepts evidence_class=real_project_headless_test"
        )
    markers = source["required_log_markers"]
    if not isinstance(markers, list) or not markers or not all(
        isinstance(marker, str) and marker for marker in markers
    ):
        raise RealGameBridgeError("source.required_log_markers must be non-empty strings")

    for key in ("fixture_id", "session_id", "player_id"):
        if not isinstance(session.get(key), str) or not session[key]:
            raise RealGameBridgeError(f"session.{key} must be a non-empty string")

    required_scenario = (
        "id",
        "step_index",
        "observation",
        "action",
        "expected_result",
        "actual_result",
        "friction",
        "category",
        "reason",
        "confusion",
        "surprise",
        "recommendation",
    )
    for key in required_scenario:
        if key not in scenario:
            raise RealGameBridgeError(f"scenario.{key} is required")

    if not isinstance(scenario["friction"], bool):
        raise RealGameBridgeError("scenario.friction must be boolean")
    for key in ("confusion", "surprise"):
        value = scenario[key]
        if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise RealGameBridgeError(f"scenario.{key} must be within 0..1")

    return record


def validate_runtime_log(record: dict[str, Any], log_path: str | Path) -> str:
    path = Path(log_path)
    try:
        log_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RealGameBridgeError(f"could not read runtime log: {path}") from exc

    missing = [
        marker
        for marker in record["source"]["required_log_markers"]
        if marker not in log_text
    ]
    if missing:
        raise RealGameBridgeError(
            "runtime log is missing required markers: " + ", ".join(missing)
        )
    return log_text


def _player_mind(record: dict[str, Any]) -> dict[str, Any]:
    scenario = record["scenario"]
    return {
        "current_goal": "Understand whether the chosen action will complete the round.",
        "perceived_goal": "Use the available evidence to decide whether to swing.",
        "expectations": [scenario["expected_result"]],
        "hypotheses": [
            "The target is close enough that the selected action may succeed."
        ],
        "uncertainties": [
            "The exact remaining distance is not directly known to the blind player."
        ],
        "attention_target": scenario["action"],
        "intended_action": scenario["action"],
        "confidence": 0.6,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run_real_game_bridge(
    record_path: str | Path,
    runtime_log_path: str | Path,
    output_root: str | Path = "evidence",
) -> RealGameBridgeRun:
    record = load_real_game_record(record_path)
    log_text = validate_runtime_log(record, runtime_log_path)

    source = record["source"]
    session_def = record["session"]
    scenario = record["scenario"]
    fixture_id = session_def["fixture_id"]
    session_id = session_def["session_id"]

    root = Path(output_root) / BRIDGE_ID / fixture_id / session_id
    mgel_root = root / "mgel"
    mgel_root.mkdir(parents=True, exist_ok=True)

    normalized_record_path = root / "source_record.json"
    runtime_snapshot_path = root / "runtime_log.txt"
    bridge_eval_path = root / "bridge_eval.json"
    manifest_path = root / "manifest.json"

    player_mind = _player_mind(record)
    event_id = "event-001"
    trace_event = {
        "event_id": event_id,
        "step_index": int(scenario["step_index"]),
        "observation": str(scenario["observation"]),
        "expectation": str(scenario["expected_result"]),
        "hypothesis": player_mind["hypotheses"][0],
        "intention": "Commit to the selected action and learn from the revealed result.",
        "action": str(scenario["action"]),
        "expected_result": str(scenario["expected_result"]),
        "actual_result": str(scenario["actual_result"]),
        "surprise": float(scenario["surprise"]),
        "confusion": float(scenario["confusion"]),
        "learned_rule": (
            "A near miss can reveal that the player was close without proving the "
            "target was reached."
        ),
        "player_mind": player_mind,
        "friction": bool(scenario["friction"]),
        "category": str(scenario["category"]),
        "recommendation": str(scenario["recommendation"]),
        "bridge_policy": {
            "psychometric_values": "deterministic_model_not_human_measurement",
            "evidence_class": source["evidence_class"],
        },
    }

    friction_event = {
        "event_id": event_id,
        "step_index": int(scenario["step_index"]),
        "action": str(scenario["action"]),
        "actual_result": str(scenario["actual_result"]),
        "surprise": float(scenario["surprise"]),
        "confusion": float(scenario["confusion"]),
        "reason": str(scenario["reason"]),
        "category": str(scenario["category"]),
        "recommendation": str(scenario["recommendation"]),
        "bridge_policy": {
            "psychometric_values": "deterministic_model_not_human_measurement",
            "evidence_class": source["evidence_class"],
        },
    }

    session_payload = {
        "fixture_id": fixture_id,
        "session_id": session_id,
        "status": "completed",
        "fresh_player": {
            "player_id": session_def["player_id"],
            "initial_game_specific_memory": {},
            "game_specific_memory": {},
        },
        "initial_player_mind": player_mind,
        "source_provenance": source,
        "scenario_id": scenario["id"],
    }
    summary = {
        "fixture_id": fixture_id,
        "session_id": session_id,
        "event_count": 1,
        "friction_count": 1 if scenario["friction"] else 0,
        "status": "completed",
    }

    _write_json(mgel_root / "session.json", session_payload)
    (mgel_root / "experience_trace.jsonl").write_text(
        json.dumps(
            trace_event,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _write_json(
        mgel_root / "friction_events.json",
        [friction_event] if scenario["friction"] else [],
    )
    _write_json(mgel_root / "summary.json", summary)
    _write_json(normalized_record_path, record)
    runtime_snapshot_path.write_text(log_text, encoding="utf-8", newline="\n")

    bridge_criteria = {
        "runtime_markers_present": True,
        "real_project_evidence_class": (
            source["evidence_class"] == "real_project_headless_test"
        ),
        "repository_provenance_present": bool(
            source["repository"]
            and source["source_head_sha"]
            and source["tested_merge_sha"]
        ),
        "workflow_provenance_present": bool(
            source["workflow_run_id"] and source["workflow_job_id"]
        ),
        "mgel_bundle_written": all(
            (mgel_root / name).is_file()
            for name in (
                "session.json",
                "experience_trace.jsonl",
                "friction_events.json",
                "summary.json",
            )
        ),
        "psychometric_policy_disclosed": (
            trace_event["bridge_policy"]["psychometric_values"]
            == "deterministic_model_not_human_measurement"
        ),
    }
    bridge_status = "PASS" if all(bridge_criteria.values()) else "FAIL"
    bridge_eval = {
        "bridge": BRIDGE_ID,
        "version": BRIDGE_VERSION,
        "status": bridge_status,
        "criteria": bridge_criteria,
        "source_repository": source["repository"],
        "workflow_run_id": source["workflow_run_id"],
        "workflow_job_id": source["workflow_job_id"],
    }
    _write_json(bridge_eval_path, bridge_eval)

    manifest = {
        "bundle_version": 1,
        "bridge": {"id": BRIDGE_ID, "version": BRIDGE_VERSION},
        "source": {
            "repository": source["repository"],
            "source_head_sha": source["source_head_sha"],
            "tested_merge_sha": source["tested_merge_sha"],
            "workflow_run_id": source["workflow_run_id"],
            "workflow_job_id": source["workflow_job_id"],
            "engine": source["engine"],
            "evidence_class": source["evidence_class"],
        },
        "artifacts": [
            "source_record.json",
            "runtime_log.txt",
            "bridge_eval.json",
            "mgel/session.json",
            "mgel/experience_trace.jsonl",
            "mgel/friction_events.json",
            "mgel/summary.json",
        ],
    }
    _write_json(manifest_path, manifest)

    return RealGameBridgeRun(
        root=root,
        mgel_root=mgel_root,
        bridge_eval_path=bridge_eval_path,
        manifest_path=manifest_path,
        normalized_record_path=normalized_record_path,
        runtime_log_path=runtime_snapshot_path,
        eval_status=bridge_status,
        fixture_id=fixture_id,
        session_id=session_id,
    )


def run_real_game_dogfood(
    record_path: str | Path,
    runtime_log_path: str | Path,
    output_root: str | Path = "evidence",
) -> RealGameDogfoodRun:
    bridge = run_real_game_bridge(record_path, runtime_log_path, output_root)
    report = run_playtest_report(bridge.mgel_root, output_root)

    report_payload = json.loads(report.report_path.read_text(encoding="utf-8"))
    finding_ids = {
        finding["source_event_id"] for finding in report_payload["findings"]
    }
    criteria = {
        "bridge_passed": bridge.eval_status == "PASS",
        "playtest_report_passed": report.eval_status == "PASS",
        "real_project_provenance_preserved": (
            report_payload["source"]["fixture_id"] == bridge.fixture_id
            and report_payload["source"]["session_id"] == bridge.session_id
        ),
        "real_game_finding_emitted": finding_ids == {"event-001"},
    }
    status = "PASS" if all(criteria.values()) else "FAIL"
    dogfood_eval_path = bridge.root / "dogfood_eval.json"
    _write_json(
        dogfood_eval_path,
        {
            "milestone": "MGSF-M0.2",
            "status": status,
            "criteria": criteria,
            "bridge_root": str(bridge.root),
            "report_root": str(report.root),
            "finding_count": report.finding_count,
        },
    )
    return RealGameDogfoodRun(
        bridge=bridge,
        report_root=report.root,
        dogfood_eval_path=dogfood_eval_path,
        status=status,
        finding_count=report.finding_count,
    )
