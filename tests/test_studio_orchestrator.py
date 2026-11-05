from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json

import pytest

from mgsf.studio_orchestrator import (
    EVIDENCE_BY_ROLE,
    build_studio_plan,
    create_studio_plan,
    evaluate_studio_evidence,
    load_studio_mission,
)


def _mission(tmp_path: Path, *, tracks: list[str] | None = None) -> Path:
    path = tmp_path / "mission.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "mission_id": "diorama-001",
        "title": "One-room diorama",
        "hypothesis": "Player understands one obvious interaction",
        "engine": "godot",
        "success_criteria": ["Playable on keyboard", "Visible response to interaction"],
        "workstreams": tracks or ["gameplay", "art", "audio"],
    }), encoding="utf-8")
    return path


def _receipts(project: Path, roles: list[str]) -> dict:
    project.mkdir(exist_ok=True)
    tasks = {}
    for role in roles:
        tasks[role] = []
        for kind in EVIDENCE_BY_ROLE[role]:
            file = project / f"{role}-{kind}.txt"
            file.write_text(f"evidence for {role}/{kind}", encoding="utf-8")
            tasks[role].append({
                "kind": kind,
                "path": file.name,
                "sha256": sha256(file.read_bytes()).hexdigest(),
            })
    return tasks


def _manifest(tmp_path: Path, tasks: dict, *, evidence_class: str = "recorded") -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "mission_id": "diorama-001",
        "evidence_class": evidence_class,
        "tasks": tasks,
    }), encoding="utf-8")
    return path


def test_plan_has_single_owner_and_qa_handoff(tmp_path: Path) -> None:
    plan = build_studio_plan(load_studio_mission(_mission(tmp_path)))
    assert [task["role"] for task in plan["tasks"]] == ["producer", "gameplay", "art", "audio", "qa"]
    assert plan["tasks"][-1]["depends_on"] == ["producer", "gameplay", "art", "audio"]
    assert plan["tasks"][1]["capability_hint"] == "Godot MCP"
    assert plan["promotion_eligible"] is False
    output = create_studio_plan(tmp_path / "mission.json", tmp_path / "plans")
    assert json.loads(output.read_text(encoding="utf-8"))["handoff_policy"]["independent_qa_required"]


def test_minimal_plan_skips_optional_tracks(tmp_path: Path) -> None:
    plan = build_studio_plan(load_studio_mission(_mission(tmp_path, tracks=["gameplay"])))
    assert [task["role"] for task in plan["tasks"]] == ["producer", "gameplay", "qa"]


@pytest.mark.parametrize("bad_id", ["../x", "foo/bar", "", "A", "."])
def test_mission_rejects_unsafe_ids(tmp_path: Path, bad_id: str) -> None:
    path = _mission(tmp_path)
    doc = json.loads(path.read_text())
    doc["mission_id"] = bad_id
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="mission_id"):
        load_studio_mission(path)


def test_duplicate_or_unknown_workstreams_are_rejected(tmp_path: Path) -> None:
    path = _mission(tmp_path)
    doc = json.loads(path.read_text())
    doc["workstreams"] = ["gameplay", "gameplay"]
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="workstreams"):
        load_studio_mission(path)
    doc["workstreams"] = ["gameplay", "untrusted-hook"]
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="workstreams"):
        load_studio_mission(path)


def test_fixture_never_promotes_even_with_all_receipts(tmp_path: Path) -> None:
    mission = _mission(tmp_path)
    project = tmp_path / "project"
    tasks = _receipts(project, ["producer", "gameplay", "art", "audio", "qa"])
    report = evaluate_studio_evidence(project, mission, _manifest(tmp_path, tasks, evidence_class="fixture"), tmp_path / "gates")
    verdict = json.loads(report.read_text())
    assert verdict["status"] == "HOLD"
    assert not verdict["missing"]
    assert verdict["promotion_eligible"] is False


def test_recorded_receipts_need_independent_review(tmp_path: Path) -> None:
    mission = _mission(tmp_path, tracks=["gameplay"])
    project = tmp_path / "project"
    tasks = _receipts(project, ["producer", "gameplay", "qa"])
    report = evaluate_studio_evidence(project, mission, _manifest(tmp_path, tasks), tmp_path / "gates")
    verdict = json.loads(report.read_text())
    assert verdict["status"] == "READY_FOR_REVIEW"
    assert len(verdict["verified_receipts"]) == 6
    assert verdict["promotion_eligible"] is False


def test_missing_and_modified_evidence_cannot_pass(tmp_path: Path) -> None:
    mission = _mission(tmp_path, tracks=["gameplay"])
    project = tmp_path / "project"
    tasks = _receipts(project, ["producer", "gameplay", "qa"])
    tasks["qa"].pop()
    (project / "gameplay-test_result.txt").write_text("mutated", encoding="utf-8")
    report = evaluate_studio_evidence(project, mission, _manifest(tmp_path, tasks), tmp_path / "gates")
    verdict = json.loads(report.read_text())
    assert verdict["status"] == "ITERATE"
    assert "qa/runner_record" in verdict["missing"]
    assert any("sha256 mismatch" in err for err in verdict["invalid"])


def test_traversal_and_duplicate_receipt_are_rejected(tmp_path: Path) -> None:
    mission = _mission(tmp_path, tracks=["gameplay"])
    project = tmp_path / "project"
    tasks = _receipts(project, ["producer", "gameplay", "qa"])
    tasks["qa"][0]["path"] = "../../outside.txt"
    tasks["gameplay"].append(dict(tasks["gameplay"][0]))
    report = evaluate_studio_evidence(project, mission, _manifest(tmp_path, tasks), tmp_path / "gates")
    verdict = json.loads(report.read_text())
    assert verdict["status"] == "ITERATE"
    assert "qa/qa_report" in verdict["missing"]
    assert any("outside project" in err for err in verdict["invalid"])
    assert any("duplicate receipt" in err for err in verdict["invalid"])
