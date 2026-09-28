from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SERVICE_ID = "playtest-report"
SERVICE_VERSION = "0.1.1"
REQUIRED_FILES = (
    "session.json",
    "experience_trace.jsonl",
    "friction_events.json",
    "summary.json",
)


class EvidenceContractError(ValueError):
    """Raised when an MGEL evidence bundle violates the M0 contract."""


@dataclass(frozen=True)
class PlaytestReportRun:
    root: Path
    report_path: Path
    markdown_path: Path
    eval_path: Path
    manifest_path: Path
    log_path: Path
    eval_status: str
    finding_count: int


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceContractError(f"could not read valid JSON: {path}") from exc


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EvidenceContractError(f"could not read JSONL: {path}") from exc

    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvidenceContractError(
                f"invalid JSONL at {path}:{index}"
            ) from exc
        if not isinstance(payload, dict):
            raise EvidenceContractError(
                f"JSONL event at {path}:{index} must be an object"
            )
        events.append(payload)
    return events


def load_mgel_bundle(root: str | Path) -> dict[str, Any]:
    bundle_root = Path(root)
    missing = [name for name in REQUIRED_FILES if not (bundle_root / name).is_file()]
    if missing:
        raise EvidenceContractError(
            "missing MGEL evidence files: " + ", ".join(sorted(missing))
        )

    session = _read_json(bundle_root / "session.json")
    trace = _read_jsonl(bundle_root / "experience_trace.jsonl")
    frictions = _read_json(bundle_root / "friction_events.json")
    summary = _read_json(bundle_root / "summary.json")

    if not isinstance(session, dict) or not isinstance(summary, dict):
        raise EvidenceContractError("session.json and summary.json must be objects")
    if not isinstance(frictions, list) or not all(
        isinstance(item, dict) for item in frictions
    ):
        raise EvidenceContractError("friction_events.json must be an array of objects")

    fixture_id = summary.get("fixture_id")
    session_id = summary.get("session_id")
    if not isinstance(fixture_id, str) or not fixture_id:
        raise EvidenceContractError("summary.fixture_id must be a non-empty string")
    if not isinstance(session_id, str) or not session_id:
        raise EvidenceContractError("summary.session_id must be a non-empty string")

    if session.get("fixture_id") != fixture_id:
        raise EvidenceContractError("fixture_id differs between session and summary")
    if session.get("session_id") != session_id:
        raise EvidenceContractError("session_id differs between session and summary")
    if summary.get("event_count") != len(trace):
        raise EvidenceContractError("summary.event_count does not match trace length")
    if summary.get("friction_count") != len(frictions):
        raise EvidenceContractError(
            "summary.friction_count does not match friction event count"
        )

    trace_ids: list[str] = []
    for event in trace:
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise EvidenceContractError("every trace event needs a non-empty event_id")
        trace_ids.append(event_id)
    if len(trace_ids) != len(set(trace_ids)):
        raise EvidenceContractError("trace event_id values must be unique")

    trace_id_set = set(trace_ids)
    for friction in frictions:
        event_id = friction.get("event_id")
        if event_id not in trace_id_set:
            raise EvidenceContractError(
                f"friction event {event_id!r} has no matching trace event"
            )

    return {
        "root": bundle_root,
        "fixture_id": fixture_id,
        "session_id": session_id,
        "session": session,
        "trace": trace,
        "frictions": frictions,
        "summary": summary,
    }


def _severity(friction: dict[str, Any]) -> str:
    confusion = float(friction.get("confusion", 0.0))
    surprise = float(friction.get("surprise", 0.0))
    signal = max(confusion, surprise)
    if signal >= 0.75:
        return "high"
    if signal >= 0.4:
        return "medium"
    return "low"


def _impact_for(severity: str) -> str:
    if severity == "high":
        return (
            "The player can become blocked or strongly uncertain because the attempted "
            "action produces no progress."
        )
    if severity == "medium":
        return (
            "The player may hesitate or repeat actions because the result conflicts "
            "with the expected path to progress."
        )
    return (
        "The player encounters a small expectation mismatch that may weaken clarity "
        "without fully blocking progress."
    )


def _default_recommendation(category: str) -> str:
    if category == "near_miss":
        return (
            "Make the miss and remaining gap legible at result time so the player can "
            "understand how close the attempt was before entering reveal."
        )
    return (
        "Clarify the prerequisite or strengthen immediate failure feedback "
        "so the player can infer the next useful action."
    )


def build_report(bundle: dict[str, Any]) -> dict[str, Any]:
    trace_by_id = {event["event_id"]: event for event in bundle["trace"]}
    findings: list[dict[str, Any]] = []

    for index, friction in enumerate(bundle["frictions"], start=1):
        trace_event = trace_by_id[friction["event_id"]]
        severity = _severity(friction)
        action = str(friction.get("action", trace_event.get("action", "unknown")))
        actual_result = str(
            friction.get("actual_result", trace_event.get("actual_result", ""))
        )
        step_index = int(friction.get("step_index", trace_event.get("step_index", 0)))
        observation = str(trace_event.get("observation", ""))
        expected_result = str(trace_event.get("expected_result", ""))
        category = str(friction.get("category", "blocked_progress"))
        title = (
            f"Action `{action}` produced a verified near miss"
            if category == "near_miss"
            else f"Action `{action}` did not advance the game state"
        )
        recommendation = str(
            friction.get("recommendation", _default_recommendation(category))
        )

        evidence = {
            "reason": str(friction.get("reason", "")),
            "confusion": float(friction.get("confusion", 0.0)),
            "surprise": float(friction.get("surprise", 0.0)),
        }
        if "bridge_policy" in friction:
            evidence["bridge_policy"] = friction["bridge_policy"]
        if "media_evidence" in friction:
            evidence["media_evidence"] = friction["media_evidence"]
        if "capture_policy" in friction:
            evidence["capture_policy"] = friction["capture_policy"]

        findings.append(
            {
                "id": f"finding-{index:03d}",
                "source_event_id": friction["event_id"],
                "step_index": step_index,
                "severity": severity,
                "category": category,
                "title": title,
                "player_impact": _impact_for(severity),
                "reproduction_steps": [
                    f"Start fixture `{bundle['fixture_id']}` with a fresh player.",
                    f"At step {step_index}, observe: {observation}",
                    f"Choose action `{action}`.",
                    f"Observe the result: {actual_result}",
                ],
                "expected_result": expected_result,
                "actual_result": actual_result,
                "recommendation": recommendation,
                "evidence": evidence,
            }
        )

    counts = {
        level: sum(1 for finding in findings if finding["severity"] == level)
        for level in ("high", "medium", "low")
    }
    return {
        "service": {"id": SERVICE_ID, "version": SERVICE_VERSION},
        "source": {
            "contract": "mgel-m0",
            "fixture_id": bundle["fixture_id"],
            "session_id": bundle["session_id"],
            "event_count": len(bundle["trace"]),
            "friction_count": len(bundle["frictions"]),
        },
        "summary": {
            "status": "findings" if findings else "clear",
            "finding_count": len(findings),
            "severity_counts": counts,
        },
        "findings": findings,
    }


def evaluate_report(bundle: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    findings = report["findings"]
    trace_ids = {event["event_id"] for event in bundle["trace"]}
    friction_ids = {event["event_id"] for event in bundle["frictions"]}
    finding_source_ids = {finding["source_event_id"] for finding in findings}

    criteria = {
        "source_identity_preserved": (
            report["source"]["fixture_id"] == bundle["fixture_id"]
            and report["source"]["session_id"] == bundle["session_id"]
        ),
        "friction_coverage_exact": (
            len(findings) == len(bundle["frictions"])
            and finding_source_ids == friction_ids
        ),
        "traceability": all(
            finding["source_event_id"] in trace_ids for finding in findings
        ),
        "actionability": all(
            bool(finding["player_impact"])
            and bool(finding["recommendation"])
            and len(finding["reproduction_steps"]) >= 3
            for finding in findings
        ),
        "severity_contract": all(
            finding["severity"] in {"high", "medium", "low"} for finding in findings
        ),
    }
    passed = all(criteria.values())
    return {
        "service": SERVICE_ID,
        "version": SERVICE_VERSION,
        "status": "PASS" if passed else "FAIL",
        "criteria": criteria,
        "finding_count": len(findings),
    }


def render_markdown(report: dict[str, Any]) -> str:
    source = report["source"]
    summary = report["summary"]
    lines = [
        "# Playtest Report",
        "",
        f"- Fixture: `{source['fixture_id']}`",
        f"- Session: `{source['session_id']}`",
        f"- Findings: {summary['finding_count']}",
        (
            "- Severity: "
            f"high={summary['severity_counts']['high']}, "
            f"medium={summary['severity_counts']['medium']}, "
            f"low={summary['severity_counts']['low']}"
        ),
        "",
    ]

    if not report["findings"]:
        lines.extend(["No friction findings were present in the source evidence.", ""])
        return "\n".join(lines)

    for finding in report["findings"]:
        lines.extend(
            [
                f"## {finding['id']}: {finding['title']}",
                "",
                f"**Severity:** {finding['severity']}",
                "",
                f"**Player impact:** {finding['player_impact']}",
                "",
                "**Reproduction:**",
            ]
        )
        for step in finding["reproduction_steps"]:
            lines.append(f"1. {step}")
        lines.extend(
            [
                "",
                f"**Expected:** {finding['expected_result']}",
                "",
                f"**Actual:** {finding['actual_result']}",
                "",
                f"**Recommendation:** {finding['recommendation']}",
                "",
                f"**Source event:** `{finding['source_event_id']}`",
                "",
            ]
        )
    return "\n".join(lines)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run_playtest_report(
    bundle_root: str | Path,
    output_root: str | Path = "evidence",
) -> PlaytestReportRun:
    bundle = load_mgel_bundle(bundle_root)
    report = build_report(bundle)
    eval_result = evaluate_report(bundle, report)

    root = (
        Path(output_root)
        / SERVICE_ID
        / bundle["fixture_id"]
        / bundle["session_id"]
    )
    root.mkdir(parents=True, exist_ok=True)

    report_path = root / "report.json"
    markdown_path = root / "report.md"
    eval_path = root / "eval.json"
    manifest_path = root / "manifest.json"
    log_path = root / "run.log"

    manifest = {
        "bundle_version": 1,
        "service": {"id": SERVICE_ID, "version": SERVICE_VERSION},
        "source": {
            "contract": "mgel-m0",
            "fixture_id": bundle["fixture_id"],
            "session_id": bundle["session_id"],
        },
        "artifacts": [
            "report.json",
            "report.md",
            "eval.json",
            "run.log",
        ],
    }

    _write_json(report_path, report)
    markdown_path.write_text(
        render_markdown(report), encoding="utf-8", newline="\n"
    )
    _write_json(eval_path, eval_result)
    _write_json(manifest_path, manifest)
    log_path.write_text(
        "\n".join(
            [
                "input_contract=mgel-m0 validated=true",
                f"events={len(bundle['trace'])}",
                f"frictions={len(bundle['frictions'])}",
                f"findings={len(report['findings'])}",
                f"eval={eval_result['status']}",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )

    return PlaytestReportRun(
        root=root,
        report_path=report_path,
        markdown_path=markdown_path,
        eval_path=eval_path,
        manifest_path=manifest_path,
        log_path=log_path,
        eval_status=eval_result["status"],
        finding_count=len(report["findings"]),
    )
