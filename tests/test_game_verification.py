from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from mgsf.game_verification import (
    GameVerificationError,
    load_game_spec,
    run_game_verification,
)

SPEC = Path("fixtures/verification/hp-game-over.yaml")
TRACE = Path("fixtures/verification/hp-game-over-trace.json")


def evaluate_changed(tmp_path: Path, edit) -> dict:
    trace = json.loads(TRACE.read_text(encoding="utf-8"))
    edit(trace)
    candidate = tmp_path / "mutated.json"
    candidate.write_text(json.dumps(trace), encoding="utf-8")
    result = run_game_verification(SPEC, candidate, tmp_path / "out")
    return json.loads((result.root / "evaluation.json").read_text(encoding="utf-8"))


def test_fixture_passes_logic_but_release_is_hold(tmp_path: Path) -> None:
    result = run_game_verification(SPEC, TRACE, tmp_path)
    assert result.verification_status == "PASS"
    assert result.status == "HOLD"
    assert result.covered_count == result.requirement_count == 2
    report = json.loads((result.root / "evaluation.json").read_text(encoding="utf-8"))
    assert report["coverage_ratio"] == 1
    assert report["human_playtest_verified"] is False
    assert report["trusted_engine_execution_verified"] is False
    for key, filename in (("spec", "spec.yaml"), ("trace", "trace.json")):
        copied = (result.root / filename).read_bytes()
        assert report["source"][key]["sha256"] == sha256(copied).hexdigest()


def test_catches_forbidden_movement_after_game_over(tmp_path: Path) -> None:
    report = evaluate_changed(
        tmp_path,
        lambda data: data["cases"][0]["steps"][3]["state_after"]["player"].update(position=99),
    )
    assert report["status"] == "FAIL"
    assert report["failed_requirements"] == ["HP-001"]
    assert report["results"][0]["checks"][3]["passed"] is False


def test_catches_wrong_score_logic(tmp_path: Path) -> None:
    report = evaluate_changed(
        tmp_path, lambda data: data["cases"][1]["steps"][0]["state_after"]["game"].update(score=0)
    )
    assert report["status"] == "FAIL"
    assert "SCORE-001" in report["failed_requirements"]


def test_catches_missing_implementation_coverage(tmp_path: Path) -> None:
    report = evaluate_changed(tmp_path, lambda data: data["cases"].pop())
    assert report["status"] == "FAIL"
    assert report["coverage_ratio"] == 0.5
    assert "SCORE-001" in report["failed_requirements"]


def test_catches_incorrect_input_replay(tmp_path: Path) -> None:
    report = evaluate_changed(
        tmp_path, lambda data: data["cases"][0]["steps"][2].update(action="enemy_miss")
    )
    assert report["status"] == "FAIL"
    assert report["results"][0]["checks"][0]["check"] == "replay_actions"
    assert report["results"][0]["checks"][0]["passed"] is False


def test_catches_missing_required_state(tmp_path: Path) -> None:
    report = evaluate_changed(
        tmp_path, lambda data: data["cases"][1]["steps"][0]["state_after"].pop("game")
    )
    assert report["status"] == "FAIL"


def test_rejects_duplicate_cases(tmp_path: Path) -> None:
    trace = json.loads(TRACE.read_text(encoding="utf-8"))
    trace["cases"].append(deepcopy(trace["cases"][0]))
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(trace), encoding="utf-8")
    with pytest.raises(GameVerificationError, match="duplicate trace case"):
        run_game_verification(SPEC, path, tmp_path / "out")


def test_rejects_claimed_live_execution_without_trusted_runner(tmp_path: Path) -> None:
    trace = json.loads(TRACE.read_text(encoding="utf-8"))
    trace["evidence_class"] = "recorded_godot_execution"
    path = tmp_path / "untrusted.json"
    path.write_text(json.dumps(trace), encoding="utf-8")
    with pytest.raises(GameVerificationError, match="trusted runner"):
        run_game_verification(SPEC, path, tmp_path / "out")


def test_rejects_undeclared_case(tmp_path: Path) -> None:
    trace = json.loads(TRACE.read_text(encoding="utf-8"))
    trace["cases"][0]["requirement_id"] = "EXTRA-001"
    path = tmp_path / "extra.json"
    path.write_text(json.dumps(trace), encoding="utf-8")
    with pytest.raises(GameVerificationError, match="undeclared trace cases"):
        run_game_verification(SPEC, path, tmp_path / "out")


def test_rejects_invalid_spec_assertion(tmp_path: Path) -> None:
    data = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    data["requirements"][0]["assertions"][0]["run_python"] = "print('not permitted')"
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(GameVerificationError, match="unsupported assertion key"):
        load_game_spec(path)


def test_cli_holds_valid_fixture(tmp_path: Path) -> None:
    cmd = [sys.executable, "-m", "mgsf.cli", "verify-game", str(SPEC),
           str(TRACE), "--output-root", str(tmp_path)]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert "gate=HOLD" in completed.stdout
    assert (tmp_path / "hp-game-over" / "evaluation.json").is_file()
