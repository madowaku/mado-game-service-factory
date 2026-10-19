from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

import pytest

from mgsf.screen_only_playtest import (
    ScreenPlaytestError,
    load_screen_mission,
    run_screen_playtest,
    verify_screen_evidence,
)


def png(r: int) -> bytes:
    def chunk(name: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + name + data + struct.pack(
            ">I", zlib.crc32(name + data) & 0xffffffff
        )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes((0, r, 10, 20))))
        + chunk(b"IEND", b"")
    )


class Port:
    def __init__(self, captures: list[bytes]) -> None:
        self.captures = iter(captures)
        self.presses: list[tuple[str, int]] = []

    def capture(self) -> bytes:
        return next(self.captures)

    def press(self, button: str, duration_ms: int) -> None:
        self.presses.append((button, duration_ms))


class Policy:
    def __init__(self, button: str = "A", duration: int = 100):
        self.button = button
        self.duration = duration
        self.calls: list[tuple[bool, bool]] = []

    def choose(self, goal, frame, history, *, rethink, evidence_needed):
        assert goal == "Reach the checkpoint"
        assert isinstance(frame, bytes)
        self.calls.append((rethink, evidence_needed))
        return ("B" if rethink else self.button), self.duration


class Judge:
    def __init__(self, verdicts: list[str]):
        self.verdicts = iter(verdicts)

    def assess(self, goal, before, after):
        return {
            "verdict": next(self.verdicts),
            "reason": "Two visible images were compared",
            "visible_before": True,
            "visible_after": True,
        }


def mission(tmp_path: Path, **overrides) -> Path:
    path = tmp_path / "mission.json"
    payload = {
        "schema_version": 1,
        "mission_id": "checkpoint-01",
        "goal": "Reach the checkpoint",
        "engine": "godot",
        "allowed_buttons": ["A", "B"],
        "max_steps": 4,
        "stall_threshold": 2,
        "rethink_budget": 1,
        **overrides,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def run(path: Path, tmp_path: Path, port: Port, policy: Policy, judge: Judge):
    return run_screen_playtest(path, port, policy, judge, tmp_path / "results",
                               policy_id="codex-policy", judge_id="independent-vlm")


def test_success_is_evidence_only_and_always_holds_promotion(tmp_path: Path):
    result = run(mission(tmp_path), tmp_path, Port([png(0), png(255)]),
                 Policy(), Judge(["PASS"]))
    assert result.status == "SCREEN_EVIDENCE_SUPPORTED"
    assert result.promotion_status == "HOLD"
    assert result.step_count == 1
    assert verify_screen_evidence(result.root)["status"] == "PASS"
    record = json.loads(result.evidence_path.read_text(encoding="utf-8"))
    assert record["source"]["internal_engine_state_used"] is False
    assert record["result"]["success_is_not_runtime_proof"] is True
    assert len(list((result.root / "frames").glob("*.png"))) == 2


def test_rethink_after_stall_and_finite_budget(tmp_path: Path):
    port = Port([png(1), png(1)] * 4)
    policy = Policy()
    result = run(mission(tmp_path), tmp_path, port, policy,
                 Judge(["FAIL"] * 4))
    assert result.status == "STALLED"
    assert result.step_count == 4
    assert result.rethink_count == 1
    assert port.presses == [("A", 100), ("A", 100), ("B", 100), ("A", 100)]
    assert policy.calls == [(False, False), (False, False), (True, False), (False, False)]
    assert verify_screen_evidence(result.root)["status"] == "PASS"


def test_missing_evidence_requests_more_observation(tmp_path: Path):
    policy = Policy()
    result = run(mission(tmp_path), tmp_path,
                 Port([png(1), png(2), png(2), png(3)]),
                 policy, Judge(["INSUFFICIENT", "PASS"]))
    assert result.status == "SCREEN_EVIDENCE_SUPPORTED"
    assert policy.calls == [(False, False), (False, True)]


def test_judge_self_report_cannot_override_unchanged_frames(tmp_path: Path):
    result = run(mission(tmp_path, max_steps=1), tmp_path,
                 Port([png(2), png(2)]), Policy(), Judge(["PASS"]))
    assert result.status == "HOLD"
    trace = json.loads((result.root / "input_evidence.jsonl").read_text(encoding="utf-8"))
    assert trace["judge"]["verdict"] == "INSUFFICIENT"
    assert verify_screen_evidence(result.root)["status"] == "PASS"


def test_invalid_action_fails_closed_without_press(tmp_path: Path):
    port = Port([png(1)])
    result = run(mission(tmp_path), tmp_path, port, Policy(button="START"), Judge(["PASS"]))
    assert result.status == "ADAPTER_FAILURE"
    assert result.step_count == 0
    assert port.presses == []
    assert verify_screen_evidence(result.root)["status"] == "PASS"


def test_invalid_duration_fails_closed(tmp_path: Path):
    result = run(mission(tmp_path), tmp_path,
                 Port([png(1)]), Policy(duration=True), Judge(["PASS"]))
    assert result.status == "ADAPTER_FAILURE"
    assert result.step_count == 0


def test_corrupt_frame_does_not_grant_proof(tmp_path: Path):
    result = run(mission(tmp_path), tmp_path,
                 Port([b"not a screenshot"]), Policy(), Judge(["PASS"]))
    assert result.status == "ADAPTER_FAILURE"
    assert result.step_count == 0


def test_judge_failure_becomes_insufficient_not_pass(tmp_path: Path):
    class BrokenJudge:
        def assess(self, *_args):
            raise RuntimeError("offline")
    result = run_screen_playtest(
        mission(tmp_path, max_steps=1), Port([png(1), png(2)]),
        Policy(), BrokenJudge(), tmp_path / "results",
        policy_id="policy", judge_id="judge",
    )
    assert result.status == "HOLD"
    assert verify_screen_evidence(result.root)["status"] == "PASS"


def test_modified_artifact_fails_audit(tmp_path: Path):
    result = run(mission(tmp_path), tmp_path, Port([png(1), png(2)]),
                 Policy(), Judge(["PASS"]))
    target = next((result.root / "frames").glob("*-after.png"))
    target.write_bytes(png(3))
    assert verify_screen_evidence(result.root)["status"] == "FAIL"


def test_path_escape_in_manifest_fails_audit(tmp_path: Path):
    result = run(mission(tmp_path), tmp_path, Port([png(1), png(2)]),
                 Policy(), Judge(["PASS"]))
    manifest = result.root / "manifest.json"
    obj = json.loads(manifest.read_text(encoding="utf-8"))
    obj["artifacts"][0]["path"] = "../../secrets.txt"
    manifest.write_text(json.dumps(obj), encoding="utf-8")
    assert verify_screen_evidence(result.root)["status"] == "FAIL"


def test_actor_identity_must_be_independent(tmp_path: Path):
    same = Policy()
    with pytest.raises(ScreenPlaytestError, match="identities must differ"):
        run_screen_playtest(
            mission(tmp_path), Port([png(1), png(2)]),
            same, same, tmp_path / "results", policy_id="same", judge_id="same",
        )


def test_mission_rejects_path_traversal_and_duplicate_inputs(tmp_path: Path):
    with pytest.raises(ScreenPlaytestError, match="safe identifier"):
        load_screen_mission(mission(tmp_path, mission_id="../escape"))
    with pytest.raises(ScreenPlaytestError, match="duplicates"):
        load_screen_mission(mission(tmp_path, allowed_buttons=["A", "A"]))


def test_mission_bounds_are_strict(tmp_path: Path):
    with pytest.raises(ScreenPlaytestError, match="max_steps"):
        load_screen_mission(mission(tmp_path, max_steps=True))
    with pytest.raises(ScreenPlaytestError, match="stall_threshold"):
        load_screen_mission(mission(tmp_path, stall_threshold=1))
    with pytest.raises(ScreenPlaytestError, match="rethink_budget"):
        load_screen_mission(mission(tmp_path, rethink_budget=-1))


def test_tampered_mission_snapshot_fails_audit(tmp_path: Path):
    result = run(mission(tmp_path), tmp_path, Port([png(1), png(2)]),
                 Policy(), Judge(["PASS"]))
    snapshot = result.root / "mission.json"
    snapshot.write_text('{"changed": true}', encoding="utf-8")
    assert verify_screen_evidence(result.root)["status"] == "FAIL"
