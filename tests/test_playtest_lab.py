from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json

import pytest

from mgsf.playtest_lab import (
    PlaytestLabError,
    compare_sessions,
    evaluate_session,
    load_scenario,
    write_refinement_brief,
)


def dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def make_session(root: Path, *, fixture: bool = True, progress: tuple[int, ...] = (1, 2, 3),
                 won: bool = True, deaths: int = 0, retries: int = 0) -> Path:
    root.mkdir(parents=True)
    scenario = {"schema_version": 1, "scenario_id": "test-scenario", "scene": "res://game.tscn",
                "state_node": ".", "steps": [{"action": "ui_right", "frames": 3}] * len(progress),
                "limits": {"max_stalls": 0, "max_deaths": 0, "max_retries": 0}}
    dump(root / "scenario.json", scenario)
    dump(root / "session.json", {
        "schema_version": 1, "scenario_id": "test-scenario", "persona": "qa", "driver": "scripted_replay",
        "source_head_sha": "a" * 40, "evidence_class": "deterministic_playtest_fixture" if fixture else "recorded_godot_playtest",
    })
    rows = [dict(step=i, action="ui_right", frames=3, state={"progress": p, "won": won if i == len(progress)-1 else False,
                         "deaths": deaths, "retries": retries}, errors=[]) for i, p in enumerate(progress)]
    (root / "trace.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    if not fixture:
        (root / "godot.stdout.txt").write_text("MGSF_PLAYTEST_OK\n", encoding="utf-8")
        (root / "godot.stderr.txt").write_text("", encoding="utf-8")
        digest = lambda name: sha256((root / name).read_bytes()).hexdigest()
        dump(root / "runner.json", {"runner": "godot-headless-script", "returncode": 0,
              "scenario_sha256": digest("scenario.json"), "trace_sha256": digest("trace.jsonl"),
              "stdout_sha256": digest("godot.stdout.txt"), "stderr_sha256": digest("godot.stderr.txt")})
    return root


def test_fixture_cannot_pass_or_generate_refinement(tmp_path: Path) -> None:
    root = make_session(tmp_path / "fixture")
    result = evaluate_session(root)
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert result.status == "HOLD"
    assert report["metrics"]["goal_reached"] is True
    assert not report["criteria"]["runner_evidence_verified"]
    with pytest.raises(PlaytestLabError, match="fixture-only"):
        write_refinement_brief(root, tmp_path / "brief")


def test_live_metrics_and_refinement_brief(tmp_path: Path) -> None:
    root = make_session(tmp_path / "live", fixture=False)
    result = evaluate_session(root)
    assert result.status == "PASS"
    brief = write_refinement_brief(root, tmp_path / "brief")
    assert "Do not publish" in brief.read_text(encoding="utf-8")


def test_bad_trace_and_tampered_runner_rejected(tmp_path: Path) -> None:
    root = make_session(tmp_path / "bad", fixture=False)
    trace = root / "trace.jsonl"
    trace.write_text(trace.read_text(encoding="utf-8").replace('"step": 1', '"step": 4'), encoding="utf-8")
    with pytest.raises(PlaytestLabError, match="non-contiguous"):
        evaluate_session(root)
    original = make_session(tmp_path / "tampered", fixture=False)
    (original / "runner.json").write_text('{"runner": "godot-headless-script", "returncode": 0}', encoding="utf-8")
    assert evaluate_session(original).status == "ITERATE"


def test_comparison_requires_same_inputs_and_live_provenance(tmp_path: Path) -> None:
    before = make_session(tmp_path / "fixture", progress=(0, 0, 0), won=False)
    after = make_session(tmp_path / "live", fixture=False)
    assert compare_sessions(before, after, tmp_path / "output").status == "HOLD"
    bad = make_session(tmp_path / "changed", fixture=False)
    data = json.loads((bad / "scenario.json").read_text())
    data["limits"]["max_stalls"] = 1
    dump(bad / "scenario.json", data)
    with pytest.raises(PlaytestLabError, match="scenario changed"):
        compare_sessions(after, bad, tmp_path / "output")


def test_improvement_regression_and_non_improving_live(tmp_path: Path) -> None:
    baseline = make_session(tmp_path / "baseline", fixture=False, progress=(0, 0, 0), won=False)
    improved = make_session(tmp_path / "improved", fixture=False, progress=(1, 2, 3), won=True)
    assert compare_sessions(baseline, improved, tmp_path / "out").status == "IMPROVED"
    assert compare_sessions(improved, baseline, tmp_path / "out").status == "REGRESSION"
    assert compare_sessions(improved, improved, tmp_path / "out").status == "UNCHANGED"


def test_invalid_scenario_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "scenario.json"
    dump(bad, {"schema_version": 1, "scenario_id": "../../escape", "scene": "res://x.tscn",
               "state_node": ".", "steps": [{"action": "ui_right", "frames": 1}],
               "limits": {"max_stalls": 0, "max_deaths": 0, "max_retries": 0}})
    with pytest.raises(PlaytestLabError, match="scenario_id"):
        load_scenario(bad)

def test_godot_script_error_prevents_pass(tmp_path: Path) -> None:
    root = make_session(tmp_path / "script-error", fixture=False)
    (root / "godot.stderr.txt").write_text("SCRIPT ERROR: Invalid call to function\n", encoding="utf-8")
    runner = json.loads((root / "runner.json").read_text(encoding="utf-8"))
    runner["stderr_sha256"] = sha256((root / "godot.stderr.txt").read_bytes()).hexdigest()
    dump(root / "runner.json", runner)
    result = evaluate_session(root)
    assert result.status == "ITERATE"
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert report["metrics"]["runtime_errors"] == 1
