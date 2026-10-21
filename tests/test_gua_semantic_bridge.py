from __future__ import annotations

import base64
import json
import struct
import zlib
from pathlib import Path

import pytest

from mgsf.gua_semantic_bridge import (
    GuaEvidenceError, StdioGuaMcp, _mission, run_gua_probe, verify_gua_evidence,
)


def png(color: int) -> bytes:
    def chunk(name: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + name + data + struct.pack(
            ">I", zlib.crc32(name + data) & 0xffffffff
        )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes((0, color, 10, 20))))
        + chunk(b"IEND", b"")
    )


class FakeGua:
    def __init__(self, *, changed: bool = True, confirmed: bool = True,
                 matching: bool = True, epoch_changed: bool = False,
                 missing_screenshot: bool = False):
        self.calls: list[str] = []
        self.changed = changed
        self.confirmed = confirmed
        self.matching = matching
        self.epoch_changed = epoch_changed
        self.missing_screenshot = missing_screenshot
        self.after = False

    def call(self, name, arguments=None):
        self.calls.append(name)
        if name == "get_ui_tree":
            return {
                "sessionEpoch": (2 if self.epoch_changed and self.after else 1),
                "frameSequence": (2 if self.after else 1),
                "screen": "Title",
                "nodes": [{"id": "Start", "role": "button", "visible": True},
                          {"id": "Next", "role": "label", "visible": self.after and self.matching}],
            }
        if name == "get_world_object_tree":
            return {"objects": [{"id": "checkpoint", "kind": "checkpoint",
                                 "state": {"reached": self.after and self.matching}}]}
        if name == "get_screenshot":
            if self.missing_screenshot:
                return {"error": "screenshot forbidden"}
            img = png(80 if self.after and self.changed else 1)
            return {"dataUri": "data:image/png;base64," + base64.b64encode(img).decode()}
        if name == "click_node":
            assert arguments == {"nodeId": "Start"}
            self.after = True
            return {"ok": True, "requestId": 17,
                    **({"completion": {"succeeded": True, "requestId": 17}} if self.confirmed else {})}
        raise AssertionError(f"unexpected Gua tool {name}")


def mission(tmp_path: Path, *, world=False, **overrides) -> Path:
    data = {
        "schema_version": 1, "mission_id": "gua-checkpoint",
        "engine": "godot", "action": {"tool": "click_node", "nodeId": "Start"},
        "expected_after": ({"tree": "world", "id": "checkpoint", "field": "state.reached", "equals": True}
                           if world else
                           {"tree": "ui", "id": "Next", "field": "visible", "equals": True}),
        **overrides,
    }
    path = tmp_path / "mission.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_hybrid_click_world_state_and_screen_comparison_hold(tmp_path):
    port = FakeGua()
    result = run_gua_probe(mission(tmp_path, world=True), port, tmp_path)
    assert result.status == "HYBRID_EVIDENCE_SUPPORTED"
    assert result.root.joinpath("before.png").is_file()
    assert port.calls == [
        "get_ui_tree", "get_world_object_tree", "get_screenshot", "click_node",
        "get_ui_tree", "get_world_object_tree", "get_screenshot",
    ]
    assert verify_gua_evidence(result.root)["status"] == "PASS"
    evidence = json.loads(result.evidence_path.read_text())
    assert evidence["result"]["promotion_status"] == "HOLD"
    assert evidence["source"]["runtime_provenance_verified"] is False


def test_visual_unchanged_semantic_only_hold(tmp_path):
    result = run_gua_probe(mission(tmp_path), FakeGua(changed=False), tmp_path)
    assert result.status == "SEMANTIC_EVIDENCE_ONLY"
    assert verify_gua_evidence(result.root)["status"] == "PASS"


@pytest.mark.parametrize("port", [
    FakeGua(confirmed=False),
    FakeGua(matching=False),
    FakeGua(epoch_changed=True),
])
def test_missing_host_completion_semantic_or_session_cannot_pass(tmp_path, port):
    result = run_gua_probe(mission(tmp_path), port, tmp_path)
    assert result.status == "HOLD"
    assert verify_gua_evidence(result.root)["status"] == "PASS"


def test_missing_screenshot_fails_closed(tmp_path):
    result = run_gua_probe(mission(tmp_path), FakeGua(missing_screenshot=True), tmp_path)
    assert result.status == "ADAPTER_FAILURE"
    assert verify_gua_evidence(result.root)["status"] == "PASS"


@pytest.mark.parametrize("invalid", [
    {"action": {"tool": "press_physical_key", "nodeId": "Start"}},
    {"action": {"tool": "click_node", "nodeId": "Start", "extra": 1}},
    {"expected_after": {"tree": "world", "id": "checkpoint", "field": "__class__", "equals": "x"}},
    {"mission_id": "../outside"},
    {"engine": "unknown"},
])
def test_invalid_missions_cannot_operate_game(tmp_path, invalid):
    port = FakeGua()
    with pytest.raises(GuaEvidenceError):
        run_gua_probe(mission(tmp_path, **invalid), port, tmp_path)
    assert port.calls == []


def test_image_mutation_fails_verifier(tmp_path):
    run = run_gua_probe(mission(tmp_path), FakeGua(), tmp_path)
    (run.root / "after.png").write_bytes(b"corrupted")
    assert verify_gua_evidence(run.root)["status"] == "FAIL"


def test_snapshot_mutation_fails_verifier(tmp_path):
    run = run_gua_probe(mission(tmp_path), FakeGua(), tmp_path)
    (run.root / "after_ui.json").write_text("{}")
    assert verify_gua_evidence(run.root)["status"] == "FAIL"


def test_unexpected_file_fails_verifier(tmp_path):
    run = run_gua_probe(mission(tmp_path), FakeGua(), tmp_path)
    (run.root / "new-secret").write_text("unexpected")
    assert verify_gua_evidence(run.root)["status"] == "FAIL"


def test_remote_bridge_denied_before_process_launch():
    with pytest.raises(GuaEvidenceError, match="local"):
        StdioGuaMcp(bridge_url="ws://192.0.2.10:8765")


def test_predicate_rejects_non_primitive_expected(tmp_path):
    with pytest.raises(GuaEvidenceError):
        _mission(json.loads(mission(tmp_path, expected_after={
            "tree": "ui", "id": "Next", "field": "visible", "equals": {"hack": True}
        }).read_text()))


def test_screenshot_mismatch_not_misrepresented_as_screen_only_success(tmp_path):
    run = run_gua_probe(mission(tmp_path), FakeGua(matching=False), tmp_path)
    evaluation = json.loads(run.evidence_path.read_text())
    assert run.status == "HOLD"
    assert evaluation["result"]["success_is_not_gameplay_proof"] is True
