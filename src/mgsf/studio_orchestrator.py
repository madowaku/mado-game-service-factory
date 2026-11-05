"""Deterministic, execution-free game-studio planning and evidence triage.

Inspired by Claude Code Game Studios' role separation; no upstream agents or
hooks are executed or installed by this module.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import re
from typing import Any


TRACKS = ("gameplay", "art", "audio")
EVIDENCE_BY_ROLE = {
    "producer": ("brief",),
    "gameplay": ("source_change", "test_result"),
    "art": ("asset_manifest", "visual_review"),
    "audio": ("audio_manifest", "audio_review"),
    "qa": ("qa_report", "gameplay_capture", "runner_record"),
}
CAPABILITY_HINTS = {
    "producer": "MADO Cockpit Operator / human decision gate",
    "art": "MGSF AI Art Director / Pixelorama",
    "audio": "MGSF Sound Identity Lab",
    "qa": "MGSF gameplay-capture / Game Test Player / Cockpit QA",
}


def _load_object(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON document must be an object")
    return value


def load_studio_mission(path: str | Path) -> dict[str, Any]:
    """Validate a small game-studio request without running any agent."""
    data = _load_object(path)
    if data.get("schema_version") != 1:
        raise ValueError("mission schema_version must be 1")
    mission_id = data.get("mission_id")
    if not isinstance(mission_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,63}", mission_id):
        raise ValueError("mission_id must be a safe lowercase path segment")
    for name in ("title", "hypothesis"):
        if not isinstance(data.get(name), str) or not data[name].strip():
            raise ValueError(f"mission {name} must be non-empty")
    criteria = data.get("success_criteria")
    if not isinstance(criteria, list) or not criteria or any(not isinstance(x, str) or not x.strip() for x in criteria):
        raise ValueError("success_criteria must be a non-empty list of non-empty strings")
    engine = data.get("engine", "godot")
    if engine not in ("godot", "edenspark"):
        raise ValueError("engine must be godot or edenspark in M0.1")
    tracks = data.get("workstreams", ["gameplay"])
    if (not isinstance(tracks, list) or not tracks or
            any(not isinstance(x, str) or x not in TRACKS for x in tracks) or
            len(set(tracks)) != len(tracks) or "gameplay" not in tracks):
        raise ValueError("workstreams must be distinct supported tracks including gameplay")
    return {
        "schema_version": 1,
        "mission_id": mission_id,
        "title": data["title"].strip(),
        "hypothesis": data["hypothesis"].strip(),
        "success_criteria": [x.strip() for x in criteria],
        "engine": engine,
        "workstreams": [x for x in TRACKS if x in tracks],
    }


def build_studio_plan(mission: dict[str, Any]) -> dict[str, Any]:
    """Compile deterministic role tasks and explicit producer/QA handoffs."""
    engine_capability = "Godot MCP" if mission["engine"] == "godot" else "EdenSpark MCP"
    roles = ["producer", *mission["workstreams"], "qa"]
    tasks = []
    for role in roles:
        depends_on = [] if role == "producer" else (["producer"] if role != "qa" else roles[:-1])
        tasks.append({
            "task_id": role,
            "role": role,
            "depends_on": depends_on,
            "capability_hint": engine_capability if role == "gameplay" else CAPABILITY_HINTS[role],
            "required_evidence": list(EVIDENCE_BY_ROLE[role]),
            "acceptance_criteria": mission["success_criteria"] if role in ("gameplay", "qa") else [],
            "status": "pending",
        })
    return {
        "schema_version": 1,
        "service": "creative-studio-orchestrator",
        "milestone": "MGSF-STUDIO-M0.1",
        "mission": mission,
        "tasks": tasks,
        "handoff_policy": {
            "execution": "advisory_only",
            "executor": "MADO Cockpit (not connected in M0.1)",
            "independent_qa_required": True,
            "human_owned_decisions": ["creative_direction", "cost", "privacy", "publish", "delete"],
        },
        "promotion_eligible": False,
    }


def create_studio_plan(mission_path: str | Path, output_root: str | Path) -> Path:
    mission = load_studio_mission(mission_path)
    root = Path(output_root) / mission["mission_id"]
    root.mkdir(parents=True, exist_ok=True)
    target = root / "studio-plan.json"
    target.write_text(json.dumps(build_studio_plan(mission), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def _validate_receipt(project: Path, task_id: str, receipt: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(receipt, dict):
        return None, f"{task_id}: receipt must be an object"
    kind, source, expected = receipt.get("kind"), receipt.get("path"), receipt.get("sha256")
    if kind not in EVIDENCE_BY_ROLE[task_id]:
        return None, f"{task_id}: unexpected evidence kind {kind!r}"
    if not isinstance(source, str) or not source or Path(source).is_absolute():
        return None, f"{task_id}/{kind}: invalid relative path"
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        return None, f"{task_id}/{kind}: invalid sha256"
    base = project.resolve()
    candidate = (base / source).resolve()
    if not candidate.is_relative_to(base) or not candidate.is_file():
        return None, f"{task_id}/{kind}: file missing or outside project"
    hasher = sha256()
    with candidate.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    if digest != expected:
        return None, f"{task_id}/{kind}: sha256 mismatch"
    return {"task_id": task_id, "kind": kind, "path": candidate.relative_to(base).as_posix(), "sha256": digest, "bytes": candidate.stat().st_size}, None


def evaluate_studio_evidence(
    project: str | Path,
    mission_path: str | Path,
    manifest_path: str | Path,
    output_root: str | Path,
) -> Path:
    """Verify file receipts, never infer a real playtest or authorize promotion."""
    mission = load_studio_mission(mission_path)
    data = _load_object(manifest_path)
    if data.get("schema_version") != 1 or data.get("mission_id") != mission["mission_id"]:
        raise ValueError("evidence manifest schema or mission_id mismatch")
    evidence_class = data.get("evidence_class")
    if evidence_class not in ("fixture", "recorded"):
        raise ValueError("evidence_class must be fixture or recorded")
    submissions = data.get("tasks", {})
    if not isinstance(submissions, dict):
        raise ValueError("tasks must be a mapping")
    plan = build_studio_plan(mission)
    roles = {task["role"] for task in plan["tasks"]}
    invalid = [f"unknown task: {role}" for role in submissions if role not in roles]
    verified: list[dict[str, Any]] = []
    missing: list[str] = []
    for task in plan["tasks"]:
        task_id = task["task_id"]
        receipts = submissions.get(task_id, [])
        if not isinstance(receipts, list):
            invalid.append(f"{task_id}: receipts must be a list")
            receipts = []
        satisfied: set[str] = set()
        for receipt in receipts:
            valid, error = _validate_receipt(Path(project), task_id, receipt)
            if error:
                invalid.append(error)
            elif valid:
                if valid["kind"] in satisfied:
                    invalid.append(f"{task_id}/{valid['kind']}: duplicate receipt")
                else:
                    satisfied.add(valid["kind"])
                    verified.append(valid)
        for kind in task["required_evidence"]:
            if kind not in satisfied:
                missing.append(f"{task_id}/{kind}")
    if evidence_class == "fixture":
        status = "HOLD"
        reason = "fixture evidence can validate contracts but cannot establish a live game result"
    elif missing or invalid:
        status = "ITERATE"
        reason = "required evidence is incomplete or invalid"
    else:
        status = "READY_FOR_REVIEW"
        reason = "receipts match files; an independent QA review must establish real runtime provenance"
    verdict = {
        "schema_version": 1,
        "service": "creative-studio-orchestrator",
        "mission_id": mission["mission_id"],
        "evidence_class": evidence_class,
        "status": status,
        "reason": reason,
        "missing": missing,
        "invalid": invalid,
        "verified_receipts": verified,
        "promotion_eligible": False,
    }
    root = Path(output_root) / mission["mission_id"]
    root.mkdir(parents=True, exist_ok=True)
    target = root / "studio-gate.json"
    target.write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
