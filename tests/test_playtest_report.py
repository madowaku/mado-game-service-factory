from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from mgsf.playtest_report import (
    EvidenceContractError,
    build_report,
    load_mgel_bundle,
    run_playtest_report,
)


FIXTURE = Path("fixtures/playtest-report/mgel-session-001")


def test_fixture_generates_one_traceable_high_severity_finding() -> None:
    bundle = load_mgel_bundle(FIXTURE)
    report = build_report(bundle)

    assert report["source"]["fixture_id"] == "fixture-001"
    assert report["summary"]["finding_count"] == 1
    finding = report["findings"][0]
    assert finding["source_event_id"] == "event-001"
    assert finding["step_index"] == 1
    assert finding["severity"] == "high"
    assert finding["category"] == "blocked_progress"
    assert len(finding["reproduction_steps"]) == 4


def test_run_writes_evidence_bundle_and_passes_eval(tmp_path: Path) -> None:
    result = run_playtest_report(FIXTURE, tmp_path)

    assert result.eval_status == "PASS"
    assert result.finding_count == 1
    assert result.report_path.is_file()
    assert result.markdown_path.is_file()
    assert result.eval_path.is_file()
    assert result.manifest_path.is_file()
    assert result.log_path.is_file()

    eval_result = json.loads(result.eval_path.read_text(encoding="utf-8"))
    assert all(eval_result["criteria"].values())

    first_report = result.report_path.read_bytes()
    second = run_playtest_report(FIXTURE, tmp_path)
    assert second.report_path.read_bytes() == first_report


def test_invalid_summary_count_fails_closed(tmp_path: Path) -> None:
    broken = tmp_path / "broken"
    shutil.copytree(FIXTURE, broken)
    summary_path = broken / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["friction_count"] = 2
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(EvidenceContractError, match="friction_count"):
        load_mgel_bundle(broken)
