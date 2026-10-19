"""Screen-only playtest loop with a fail-closed evidence and Rethink boundary.

The host supplies an explicitly approved controller/capture port and two independent
model adapters. This module does not install engines, call hosted models, or promote
mock runs to real gameplay proof.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import uuid
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


SERVICE = "screen-only-autonomous-playtest"
BUTTONS = frozenset({"A", "B", "X", "Y", "UP", "DOWN", "LEFT", "RIGHT", "START", "SELECT"})
MAX_FRAME_BYTES = 10 * 1024 * 1024
MISSION_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}$")


class ScreenPlaytestError(ValueError):
    """Invalid mission, media or adapter output."""


class ScreenPort(Protocol):
    def capture(self) -> bytes:
        """Return a current screenshot (PNG or JPEG), never internal game state."""
        ...

    def press(self, button: str, duration_ms: int) -> None:
        """Send a bounded virtual controller input."""
        ...


class ScreenPolicy(Protocol):
    def choose(self, goal: str, frame: bytes, history: tuple[dict[str, Any], ...],
               *, rethink: bool, evidence_needed: bool) -> tuple[str, int]:
        """Select one controller input using only screenshots and prior actions."""
        ...


class IndependentJudge(Protocol):
    def assess(self, goal: str, before: bytes, after: bytes) -> dict[str, Any]:
        """Return verdict, reason, visible_before, visible_after from screen evidence."""
        ...


@dataclass(frozen=True)
class Mission:
    mission_id: str
    goal: str
    engine: str
    max_steps: int
    stall_threshold: int
    rethink_budget: int
    allowed_buttons: frozenset[str]


@dataclass(frozen=True)
class ScreenPlaytestResult:
    root: Path
    evidence_path: Path
    status: str
    promotion_status: str
    step_count: int
    rethink_count: int


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _number(value: Any, minimum: int, maximum: int, key: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ScreenPlaytestError(f"{key} must be an integer in {minimum}..{maximum}")
    return value


def load_screen_mission(path: str | Path) -> Mission:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ScreenPlaytestError("mission schema_version must be 1")
    mission_id = raw.get("mission_id")
    if not isinstance(mission_id, str) or not MISSION_ID.fullmatch(mission_id) or mission_id in {".", ".."}:
        raise ScreenPlaytestError("mission_id must be a safe identifier")
    goal = raw.get("goal")
    if not isinstance(goal, str) or not goal.strip() or len(goal) > 2000:
        raise ScreenPlaytestError("goal must be non-empty and at most 2000 characters")
    engine = raw.get("engine")
    if engine not in {"godot", "unity", "other"}:
        raise ScreenPlaytestError("engine must be godot, unity or other")
    buttons = raw.get("allowed_buttons", ["A", "B", "UP", "DOWN", "LEFT", "RIGHT"])
    if not isinstance(buttons, list) or not buttons or any(not isinstance(b, str) or b not in BUTTONS for b in buttons):
        raise ScreenPlaytestError("allowed_buttons contains an unsupported gamepad input")
    if len(set(buttons)) != len(buttons):
        raise ScreenPlaytestError("allowed_buttons must not contain duplicates")
    return Mission(
        mission_id=mission_id, goal=goal.strip(), engine=engine,
        max_steps=_number(raw.get("max_steps", 12), 1, 100, "max_steps"),
        stall_threshold=_number(raw.get("stall_threshold", 3), 2, 10, "stall_threshold"),
        rethink_budget=_number(raw.get("rethink_budget", 2), 0, 10, "rethink_budget"),
        allowed_buttons=frozenset(buttons),
    )


def _image(data: bytes) -> str:
    if not isinstance(data, bytes) or not (32 <= len(data) <= MAX_FRAME_BYTES):
        raise ScreenPlaytestError("capture must be non-empty bounded image bytes")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        pos, width, height, idat, done = 8, 0, 0, False, False
        while pos + 12 <= len(data):
            size = struct.unpack(">I", data[pos:pos + 4])[0]
            if size > MAX_FRAME_BYTES or pos + 12 + size > len(data):
                break
            name = data[pos + 4:pos + 8]
            payload = data[pos + 8:pos + 8 + size]
            crc = struct.unpack(">I", data[pos + 8 + size:pos + 12 + size])[0]
            if (zlib.crc32(name + payload) & 0xffffffff) != crc:
                break
            if name == b"IHDR" and pos == 8 and size == 13:
                width, height = struct.unpack(">II", payload[:8])
            if name == b"IDAT":
                idat = True
            pos += size + 12
            if name == b"IEND" and size == 0:
                done = pos == len(data)
                break
        if done and idat and 0 < width <= 16384 and 0 < height <= 16384:
            return ".png"
    if data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9"):
        return ".jpg"
    raise ScreenPlaytestError("capture is not a structurally valid PNG/JPEG")


def _judgement(value: Any, changed: bool) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"verdict": "INSUFFICIENT", "reason": "judge contract missing", "evidence_supported": False}
    verdict = value.get("verdict")
    reason = value.get("reason")
    if verdict not in {"PASS", "FAIL", "INSUFFICIENT"} or not isinstance(reason, str) or not reason.strip():
        return {"verdict": "INSUFFICIENT", "reason": "judge contract invalid", "evidence_supported": False}
    visible = value.get("visible_before") is True and value.get("visible_after") is True
    supported = verdict == "PASS" and changed and visible
    return {
        "verdict": verdict if supported or verdict != "PASS" else "INSUFFICIENT",
        "reason": reason[:1000],
        "visible_before": value.get("visible_before") is True,
        "visible_after": value.get("visible_after") is True,
        "evidence_supported": supported,
    }


def run_screen_playtest(
    mission_path: str | Path,
    port: ScreenPort,
    policy: ScreenPolicy,
    judge: IndependentJudge,
    output_root: str | Path = "evidence",
    *,
    policy_id: str,
    judge_id: str,
    evidence_class: str = "deterministic_mock_screen_fixture",
) -> ScreenPlaytestResult:
    """Run a bounded, screen-only closed loop against a supplied game adapter.

    Run adapters are injected deliberately. A real run must use a verified capture/input
    port and independently operated judge, not a fabricated model receipt.
    """
    mission = load_screen_mission(mission_path)
    mission_bytes = Path(mission_path).read_bytes()
    if not policy_id.strip() or not judge_id.strip() or policy_id == judge_id or policy is judge:
        raise ScreenPlaytestError("policy and independent judge identities must differ")
    if evidence_class not in {"deterministic_mock_screen_fixture", "recorded_screen_port_run"}:
        raise ScreenPlaytestError("unsupported evidence_class")
    root = Path(output_root) / SERVICE / mission.mission_id / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=False)
    frames = root / "frames"
    frames.mkdir()
    (root / "mission.json").write_bytes(mission_bytes)
    history: list[dict[str, Any]] = []
    failure: str | None = None
    status, pending_rethink, evidence_needed = "HOLD", False, False
    stagnant, rethink_count = 0, 0
    for step in range(1, mission.max_steps + 1):
        try:
            before = port.capture()
            before_ext = _image(before)
            button, duration_ms = policy.choose(
                mission.goal, before, tuple(dict(item) for item in history),
                rethink=pending_rethink, evidence_needed=evidence_needed,
            )
            if button not in mission.allowed_buttons:
                raise ScreenPlaytestError(f"controller input {button!r} not allowlisted")
            _number(duration_ms, 30, 2000, "duration_ms")
            pending_rethink = False
            port.press(button, duration_ms)
            after = port.capture()
            after_ext = _image(after)
            before_sha, after_sha = _hash(before), _hash(after)
            before_name = f"{step:03d}-before{before_ext}"
            after_name = f"{step:03d}-after{after_ext}"
            (frames / before_name).write_bytes(before)
            (frames / after_name).write_bytes(after)
            changed = before_sha != after_sha
            try:
                raw_judgement = judge.assess(mission.goal, before, after)
            except Exception as exc:  # an unavailable judge never grants PASS
                raw_judgement = {"verdict": "INSUFFICIENT", "reason": f"judge unavailable: {type(exc).__name__}"}
            judgement = _judgement(raw_judgement, changed)
            stagnant = 0 if changed else stagnant + 1
            entry = {
                "step": step, "button": button, "duration_ms": duration_ms,
                "before": {"path": f"frames/{before_name}", "sha256": before_sha},
                "after": {"path": f"frames/{after_name}", "sha256": after_sha},
                "visible_frame_changed": changed, "judge": judgement,
                "rethink_triggered": False,
            }
            history.append(entry)
            if judgement["evidence_supported"]:
                status = "SCREEN_EVIDENCE_SUPPORTED"
                break
            evidence_needed = judgement["verdict"] == "INSUFFICIENT"
            if stagnant >= mission.stall_threshold:
                if rethink_count >= mission.rethink_budget:
                    status = "STALLED"
                    break
                rethink_count += 1
                entry["rethink_triggered"] = True
                pending_rethink = True
                stagnant = 0
        except Exception as exc:  # adapter/runtime exhaustion must still leave auditable HOLD evidence
            failure = f"{type(exc).__name__}: {str(exc)[:300]}"
            status = "ADAPTER_FAILURE"
            break

    trace_path = root / "input_evidence.jsonl"
    trace_path.write_text(
        "".join(json.dumps(item, sort_keys=True, ensure_ascii=False) + "\n" for item in history),
        encoding="utf-8",
    )
    record = {
        "schema_version": 1, "service": SERVICE,
        "mission": {"id": mission.mission_id, "goal": mission.goal, "engine": mission.engine,
                    "sha256": _hash(mission_bytes)},
        "actors": {"policy": policy_id, "judge": judge_id, "independent": policy_id != judge_id},
        "source": {"evidence_class": evidence_class, "screen_only": True,
                   "controller_only": True, "internal_engine_state_used": False},
        "result": {"status": status, "promotion_status": "HOLD",
                   "success_is_not_runtime_proof": True,
                   "step_count": len(history), "rethink_count": rethink_count,
                   "failure": failure},
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
    }
    evidence_path = root / "evaluation.json"
    _json(evidence_path, record)
    files = [evidence_path, trace_path, root / "mission.json", *sorted(frames.iterdir())]
    _json(root / "manifest.json", {
        "schema_version": 1,
        "artifacts": [{"path": path.relative_to(root).as_posix(), "sha256": _hash(path.read_bytes()),
                       "bytes": path.stat().st_size} for path in files],
    })
    return ScreenPlaytestResult(root, evidence_path, status, "HOLD", len(history), rethink_count)


def verify_screen_evidence(root: str | Path) -> dict[str, Any]:
    """Audit a bundle's hashes and step-to-frame bindings; never promote it."""
    root = Path(root).resolve()
    try:
        record = json.loads((root / "evaluation.json").read_text(encoding="utf-8"))
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        trace = [json.loads(line) for line in (root / "input_evidence.jsonl").read_text(encoding="utf-8").splitlines()]
        artifacts = manifest["artifacts"]
        valid = manifest["schema_version"] == record["schema_version"] == 1
        seen: set[str] = set()
        for item in artifacts:
            rel = item["path"]
            path = (root / rel).resolve()
            if rel in seen or not path.is_relative_to(root) or not path.is_file():
                valid = False
                break
            seen.add(rel)
            valid &= path.stat().st_size == item["bytes"] and _hash(path.read_bytes()) == item["sha256"]
        expected = {"evaluation.json", "input_evidence.jsonl", "mission.json"}
        valid &= _hash((root / "mission.json").read_bytes()) == record["mission"]["sha256"]
        for i, entry in enumerate(trace, 1):
            valid &= entry["step"] == i
            for key in ("before", "after"):
                source = entry[key]
                expected.add(source["path"])
                file = (root / source["path"]).resolve()
                valid &= file.is_relative_to(root) and file.is_file()
                if file.is_file() and file.is_relative_to(root):
                    valid &= _hash(file.read_bytes()) == source["sha256"]
            valid &= entry["visible_frame_changed"] == (entry["before"]["sha256"] != entry["after"]["sha256"])
            valid &= not entry["judge"]["evidence_supported"] or (
                entry["judge"]["verdict"] == "PASS" and entry["visible_frame_changed"]
                and entry["judge"]["visible_before"] and entry["judge"]["visible_after"])
        valid &= seen == expected
        valid &= record["result"]["step_count"] == len(trace)
        valid &= record["result"]["promotion_status"] == "HOLD"
        valid &= record["actors"]["policy"] != record["actors"]["judge"]
        valid &= record["source"]["screen_only"] is True
        valid &= record["result"]["status"] != "SCREEN_EVIDENCE_SUPPORTED" or (
            bool(trace) and trace[-1]["judge"]["evidence_supported"])
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        valid = False
    return {"status": "PASS" if valid else "FAIL", "promotion_status": "HOLD", "artifact_root": str(root)}
