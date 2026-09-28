from __future__ import annotations

import json
from pathlib import Path

import pytest

from mgsf.real_game_bridge import (
    RealGameBridgeError,
    load_real_game_record,
    run_real_game_bridge,
    run_real_game_dogfood,
)


RECORD = Path("dogfood/vertical-slice-c6-near-miss/record.json")
LOG = Path("dogfood/vertical-slice-c6-near-miss/runtime_log.txt")


def test_real_game_bridge_writes_mgel_bundle_with_provenance(tmp_path: Path) -> None:
    result = run_real_game_bridge(RECORD, LOG, tmp_path)

    assert result.eval_status == "PASS"
    assert result.fixture_id == "vertical-slice-c6-near-miss"
    assert result.session_id == "dogfood-001"

    session = json.loads(
        (result.mgel_root / "session.json").read_text(encoding="utf-8")
    )
    assert session["source_provenance"]["repository"] == "madowaku/vertical-slice"
    assert (
        session["source_provenance"]["evidence_class"]
        == "real_project_headless_test"
    )

    trace = json.loads(
        (result.mgel_root / "experience_trace.jsonl")
        .read_text(encoding="utf-8")
        .strip()
    )
    assert (
        trace["bridge_policy"]["psychometric_values"]
        == "deterministic_model_not_human_measurement"
    )


def test_real_game_dogfood_reaches_playtest_report(tmp_path: Path) -> None:
    result = run_real_game_dogfood(RECORD, LOG, tmp_path)

    assert result.status == "PASS"
    assert result.finding_count == 1

    report = json.loads((result.report_root / "report.json").read_text(encoding="utf-8"))
    finding = report["findings"][0]
    assert finding["source_event_id"] == "event-001"
    assert finding["category"] == "near_miss"
    assert finding["severity"] == "medium"


def test_bridge_rejects_runtime_log_without_required_marker(tmp_path: Path) -> None:
    record = load_real_game_record(RECORD)
    assert record["source"]["workflow_run_id"] == 33968989364

    bad_log = tmp_path / "bad.log"
    bad_log.write_text("Failures: 0\n", encoding="utf-8")

    with pytest.raises(RealGameBridgeError, match="missing required markers"):
        run_real_game_bridge(RECORD, bad_log, tmp_path / "out")
