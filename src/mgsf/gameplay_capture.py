from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .playtest_report import run_playtest_report

CAPTURE_SERVICE_ID = "gameplay-capture"
CAPTURE_SERVICE_VERSION = "0.3.1"
ALLOWED_EVIDENCE_CLASSES = {
    "recorded_gameplay_capture",
    "reconstructed_from_verified_state",
    "synthetic_capture_fixture",
}
ALLOWED_MEDIA_KINDS = {"frame", "video"}
ALLOWED_MEDIA_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".svg",
    ".gif",
    ".mp4",
    ".webm",
    ".mov",
}
REQUIRED_FRICTION_FIELDS = {
    "action",
    "expected_result",
    "actual_result",
    "confusion",
    "surprise",
    "reason",
    "recommendation",
}


class GameplayCaptureError(ValueError):
    """Raised when capture evidence violates the MGSF-M0.3 contract."""


@dataclass(frozen=True)
class GameplayCaptureRun:
    root: Path
    manifest_path: Path
    media_index_path: Path
    timeline_path: Path
    eval_path: Path
    eval_status: str
    capture_id: str
    session_id: str
    media_count: int
    event_count: int


@dataclass(frozen=True)
class CapturePlaytestRun:
    capture: GameplayCaptureRun
    mgel_root: Path
    report_root: Path
    eval_path: Path
    status: str
    finding_count: int


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GameplayCaptureError(f"could not read valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise GameplayCaptureError(f"JSON root must be an object: {path}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise GameplayCaptureError(f"could not read JSONL: {path}") from exc

    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GameplayCaptureError(
                f"invalid JSONL at {path}:{line_number}"
            ) from exc
        if not isinstance(payload, dict):
            raise GameplayCaptureError(
                f"timeline event at {path}:{line_number} must be an object"
            )
        events.append(payload)
    return events


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _validate_friction_event(event: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_FRICTION_FIELDS - set(event))
    if missing:
        raise GameplayCaptureError(
            f"{event.get('event_id', 'friction')} missing fields: {', '.join(missing)}"
        )
    for key in ("confusion", "surprise"):
        value = event[key]
        if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise GameplayCaptureError(
                f"{event.get('event_id', 'friction')}.{key} must be within 0..1"
            )
    media_ids = event.get("evidence_media_ids", [])
    if not isinstance(media_ids, list) or not all(
        isinstance(media_id, str) and media_id for media_id in media_ids
    ):
        raise GameplayCaptureError(
            f"{event.get('event_id', 'friction')}.evidence_media_ids must be strings"
        )


def load_capture_session(root: str | Path) -> dict[str, Any]:
    capture_root = Path(root)
    manifest_path = capture_root / "capture.json"
    timeline_path = capture_root / "timeline.jsonl"

    if not manifest_path.is_file():
        raise GameplayCaptureError("capture.json is required")
    if not timeline_path.is_file():
        raise GameplayCaptureError("timeline.jsonl is required")

    manifest = _read_json(manifest_path)
    timeline = _read_jsonl(timeline_path)

    if manifest.get("version") != 1:
        raise GameplayCaptureError("capture version must be 1")

    for key in ("capture_id", "session_id"):
        value = manifest.get(key)
        if not isinstance(value, str) or not value:
            raise GameplayCaptureError(f"{key} must be a non-empty string")

    source = manifest.get("source")
    if not isinstance(source, dict):
        raise GameplayCaptureError("source must be an object")

    evidence_class = source.get("evidence_class")
    if evidence_class not in ALLOWED_EVIDENCE_CLASSES:
        raise GameplayCaptureError(
            f"unsupported source.evidence_class: {evidence_class!r}"
        )

    media = manifest.get("media")
    if not isinstance(media, list) or not media:
        raise GameplayCaptureError("media must be a non-empty array")

    media_ids: set[str] = set()
    normalized_media: list[dict[str, Any]] = []
    for item in media:
        if not isinstance(item, dict):
            raise GameplayCaptureError("each media entry must be an object")
        media_id = item.get("id")
        relative_path = item.get("path")
        kind = item.get("kind")
        at_ms = item.get("at_ms")

        if not isinstance(media_id, str) or not media_id:
            raise GameplayCaptureError("media.id must be a non-empty string")
        if media_id in media_ids:
            raise GameplayCaptureError(f"duplicate media id: {media_id}")
        media_ids.add(media_id)

        if not isinstance(relative_path, str) or not relative_path:
            raise GameplayCaptureError(f"media {media_id} needs a path")
        if kind not in ALLOWED_MEDIA_KINDS:
            raise GameplayCaptureError(f"media {media_id} has invalid kind: {kind}")
        if not isinstance(at_ms, int) or at_ms < 0:
            raise GameplayCaptureError(f"media {media_id}.at_ms must be >= 0")

        source_path = capture_root / relative_path
        if not source_path.is_file():
            raise GameplayCaptureError(
                f"media {media_id} file does not exist: {relative_path}"
            )
        if source_path.suffix.lower() not in ALLOWED_MEDIA_SUFFIXES:
            raise GameplayCaptureError(
                f"media {media_id} has unsupported suffix: {source_path.suffix}"
            )
        size = source_path.stat().st_size
        if size <= 0:
            raise GameplayCaptureError(f"media {media_id} is empty")

        normalized_media.append(
            {
                **item,
                "bytes": size,
                "sha256": _sha256(source_path),
                "_source_path": source_path,
            }
        )

    if not timeline:
        raise GameplayCaptureError("timeline must contain at least one event")

    event_ids: set[str] = set()
    previous_at_ms = -1
    input_count = 0
    observation_count = 0
    friction_count = 0
    normalized_timeline: list[dict[str, Any]] = []

    for event in timeline:
        event_id = event.get("event_id")
        at_ms = event.get("at_ms")
        kind = event.get("kind")
        if not isinstance(event_id, str) or not event_id:
            raise GameplayCaptureError("every timeline event needs event_id")
        if event_id in event_ids:
            raise GameplayCaptureError(f"duplicate timeline event_id: {event_id}")
        event_ids.add(event_id)

        if not isinstance(at_ms, int) or at_ms < 0:
            raise GameplayCaptureError(f"{event_id}.at_ms must be >= 0")
        if at_ms < previous_at_ms:
            raise GameplayCaptureError("timeline timestamps must be monotonic")
        previous_at_ms = at_ms

        if not isinstance(kind, str) or not kind:
            raise GameplayCaptureError(f"{event_id}.kind must be a non-empty string")
        if kind == "input":
            input_count += 1
        if kind in {"observation", "result", "friction"}:
            observation_count += 1
        if kind == "friction":
            friction_count += 1
            _validate_friction_event(event)

        referenced_media = []
        if event.get("media_id") is not None:
            referenced_media.append(event["media_id"])
        referenced_media.extend(event.get("evidence_media_ids", []))
        for media_id in referenced_media:
            if media_id not in media_ids:
                raise GameplayCaptureError(
                    f"{event_id} references unknown media_id: {media_id}"
                )
        normalized_timeline.append(event)

    if input_count < 1:
        raise GameplayCaptureError("timeline must contain at least one input event")
    if observation_count < 1:
        raise GameplayCaptureError(
            "timeline must contain observation, result, or friction evidence"
        )

    return {
        "root": capture_root,
        "manifest": manifest,
        "timeline": normalized_timeline,
        "media": normalized_media,
        "capture_id": manifest["capture_id"],
        "session_id": manifest["session_id"],
        "source": source,
        "input_count": input_count,
        "observation_count": observation_count,
        "friction_count": friction_count,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run_gameplay_capture(
    capture_root: str | Path,
    output_root: str | Path = "evidence",
) -> GameplayCaptureRun:
    session = load_capture_session(capture_root)
    root = (
        Path(output_root)
        / CAPTURE_SERVICE_ID
        / session["capture_id"]
        / session["session_id"]
    )
    media_root = root / "media"
    media_root.mkdir(parents=True, exist_ok=True)

    media_index: list[dict[str, Any]] = []
    for item in session["media"]:
        source_path: Path = item["_source_path"]
        destination = media_root / source_path.name
        shutil.copyfile(source_path, destination)
        media_index.append(
            {
                key: value
                for key, value in item.items()
                if key != "_source_path"
            }
            | {"copied_path": f"media/{destination.name}"}
        )

    timeline_path = root / "timeline.jsonl"
    timeline_path.write_text(
        "".join(
            json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for event in session["timeline"]
        ),
        encoding="utf-8",
        newline="\n",
    )

    media_index_path = root / "media_index.json"
    _write_json(media_index_path, media_index)

    media_id_set = {item["id"] for item in media_index}
    criteria = {
        "media_present": len(media_index) > 0,
        "media_integrity_indexed": all(
            item["bytes"] > 0 and len(item["sha256"]) == 64 for item in media_index
        ),
        "timeline_present": len(session["timeline"]) > 0,
        "input_trace_present": session["input_count"] > 0,
        "observable_result_present": session["observation_count"] > 0,
        "media_traceable": all(
            (
                event.get("media_id") is None
                or event["media_id"] in media_id_set
            )
            and all(
                media_id in media_id_set
                for media_id in event.get("evidence_media_ids", [])
            )
            for event in session["timeline"]
        ),
        "evidence_class_disclosed": (
            session["source"]["evidence_class"] in ALLOWED_EVIDENCE_CLASSES
        ),
    }
    status = "PASS" if all(criteria.values()) else "FAIL"

    eval_path = root / "eval.json"
    _write_json(
        eval_path,
        {
            "service": CAPTURE_SERVICE_ID,
            "version": CAPTURE_SERVICE_VERSION,
            "status": status,
            "criteria": criteria,
            "media_count": len(media_index),
            "event_count": len(session["timeline"]),
            "friction_count": session["friction_count"],
        },
    )

    manifest_path = root / "manifest.json"
    _write_json(
        manifest_path,
        {
            "bundle_version": 1,
            "service": {
                "id": CAPTURE_SERVICE_ID,
                "version": CAPTURE_SERVICE_VERSION,
            },
            "capture_id": session["capture_id"],
            "session_id": session["session_id"],
            "source": session["source"],
            "artifacts": [
                "media_index.json",
                "timeline.jsonl",
                "eval.json",
                *[item["copied_path"] for item in media_index],
            ],
        },
    )

    return GameplayCaptureRun(
        root=root,
        manifest_path=manifest_path,
        media_index_path=media_index_path,
        timeline_path=timeline_path,
        eval_path=eval_path,
        eval_status=status,
        capture_id=session["capture_id"],
        session_id=session["session_id"],
        media_count=len(media_index),
        event_count=len(session["timeline"]),
    )


def _nearest_observation(timeline: list[dict[str, Any]], target_index: int) -> str:
    for event in reversed(timeline[: target_index + 1]):
        if event["kind"] == "observation":
            return str(event.get("label", "Observed gameplay state."))
    return "Observed gameplay state."


def _media_evidence(
    media_index: list[dict[str, Any]],
    media_ids: list[str],
) -> list[dict[str, Any]]:
    by_id = {item["id"]: item for item in media_index}
    return [
        {
            "media_id": media_id,
            "kind": by_id[media_id]["kind"],
            "at_ms": by_id[media_id]["at_ms"],
            "sha256": by_id[media_id]["sha256"],
            "bytes": by_id[media_id]["bytes"],
            "path": by_id[media_id]["copied_path"],
        }
        for media_id in media_ids
    ]


def bridge_capture_to_mgel(
    capture_root: str | Path,
    capture_result: GameplayCaptureRun,
) -> Path:
    session = load_capture_session(capture_root)
    media_index = json.loads(
        capture_result.media_index_path.read_text(encoding="utf-8")
    )
    friction_events = [
        (index, event)
        for index, event in enumerate(session["timeline"])
        if event["kind"] == "friction"
    ]
    if not friction_events:
        raise GameplayCaptureError(
            "capture-to-playtest bridge needs at least one friction event"
        )

    mgel_root = capture_result.root / "mgel"
    mgel_root.mkdir(parents=True, exist_ok=True)

    traces: list[dict[str, Any]] = []
    frictions: list[dict[str, Any]] = []
    for step_index, (timeline_index, event) in enumerate(friction_events, start=1):
        media_ids = list(event.get("evidence_media_ids", []))
        if event.get("media_id") and event["media_id"] not in media_ids:
            media_ids.insert(0, event["media_id"])
        media = _media_evidence(media_index, media_ids)
        observation = _nearest_observation(session["timeline"], timeline_index)
        event_id = str(event["event_id"])
        category = str(event.get("category", "captured_friction"))
        recommendation = str(event["recommendation"])

        traces.append(
            {
                "event_id": event_id,
                "step_index": step_index,
                "observation": observation,
                "expectation": str(event["expected_result"]),
                "hypothesis": "The selected input should produce the expected outcome.",
                "intention": "Use the captured input and observed result to update the playtest model.",
                "action": str(event["action"]),
                "expected_result": str(event["expected_result"]),
                "actual_result": str(event["actual_result"]),
                "surprise": float(event["surprise"]),
                "confusion": float(event["confusion"]),
                "learned_rule": "Captured media can anchor the mismatch between expected and observed play.",
                "player_mind": {
                    "current_goal": "Understand the observed gameplay outcome.",
                    "perceived_goal": "Determine whether the captured input achieved the intended result.",
                    "expectations": [str(event["expected_result"])],
                    "hypotheses": [
                        "The selected input should produce the expected outcome."
                    ],
                    "uncertainties": [
                        "The player-state values are modeled unless human telemetry is supplied."
                    ],
                    "attention_target": str(event["action"]),
                    "intended_action": str(event["action"]),
                    "confidence": 0.6,
                },
                "friction": True,
                "category": category,
                "recommendation": recommendation,
                "media_evidence": media,
                "capture_policy": {
                    "evidence_class": session["source"]["evidence_class"],
                    "media_is_direct_gameplay": (
                        session["source"]["evidence_class"]
                        == "recorded_gameplay_capture"
                    ),
                },
            }
        )
        frictions.append(
            {
                "event_id": event_id,
                "step_index": step_index,
                "action": str(event["action"]),
                "actual_result": str(event["actual_result"]),
                "surprise": float(event["surprise"]),
                "confusion": float(event["confusion"]),
                "reason": str(event["reason"]),
                "category": category,
                "recommendation": recommendation,
                "media_evidence": media,
                "capture_policy": {
                    "evidence_class": session["source"]["evidence_class"],
                    "media_is_direct_gameplay": (
                        session["source"]["evidence_class"]
                        == "recorded_gameplay_capture"
                    ),
                },
            }
        )

    fixture_id = session["capture_id"]
    session_id = session["session_id"]
    _write_json(
        mgel_root / "session.json",
        {
            "fixture_id": fixture_id,
            "session_id": session_id,
            "status": "completed",
            "fresh_player": {
                "player_id": "capture-player-001",
                "initial_game_specific_memory": {},
                "game_specific_memory": {},
            },
            "initial_player_mind": traces[0]["player_mind"],
            "source_provenance": session["source"],
            "capture_manifest": str(capture_result.manifest_path),
        },
    )
    (mgel_root / "experience_trace.jsonl").write_text(
        "".join(
            json.dumps(trace, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for trace in traces
        ),
        encoding="utf-8",
        newline="\n",
    )
    _write_json(mgel_root / "friction_events.json", frictions)
    _write_json(
        mgel_root / "summary.json",
        {
            "fixture_id": fixture_id,
            "session_id": session_id,
            "event_count": len(traces),
            "friction_count": len(frictions),
            "status": "completed",
        },
    )
    return mgel_root


def run_capture_playtest(
    capture_root: str | Path,
    output_root: str | Path = "evidence",
) -> CapturePlaytestRun:
    capture = run_gameplay_capture(capture_root, output_root)
    mgel_root = bridge_capture_to_mgel(capture_root, capture)
    report = run_playtest_report(mgel_root, output_root)
    report_payload = json.loads(report.report_path.read_text(encoding="utf-8"))

    media_linked = all(
        bool(finding["evidence"].get("media_evidence"))
        for finding in report_payload["findings"]
    )
    criteria = {
        "capture_eval_passed": capture.eval_status == "PASS",
        "mgel_bridge_written": mgel_root.is_dir(),
        "playtest_report_passed": report.eval_status == "PASS",
        "media_evidence_reaches_findings": media_linked,
        "evidence_class_preserved": all(
            finding["evidence"].get("capture_policy", {}).get("evidence_class")
            == load_capture_session(capture_root)["source"]["evidence_class"]
            for finding in report_payload["findings"]
        ),
    }
    status = "PASS" if all(criteria.values()) else "FAIL"
    eval_path = capture.root / "capture_playtest_eval.json"
    _write_json(
        eval_path,
        {
            "milestone": "MGSF-M0.3",
            "status": status,
            "criteria": criteria,
            "finding_count": report.finding_count,
            "report_root": str(report.root),
            "evidence_class": load_capture_session(capture_root)["source"][
                "evidence_class"
            ],
        },
    )
    return CapturePlaytestRun(
        capture=capture,
        mgel_root=mgel_root,
        report_root=report.root,
        eval_path=eval_path,
        status=status,
        finding_count=report.finding_count,
    )
