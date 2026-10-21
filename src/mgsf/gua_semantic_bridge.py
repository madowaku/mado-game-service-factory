"""Opt-in Gua MCP semantic/visual evidence bridge (MGSF-M1.2).

Only approved read-only observations and one explicit click_node can be sent.
A mock transcript is contract evidence, never live gameplay proof.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import queue
import re
import subprocess
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .screen_only_playtest import _image

SERVICE = "gua-hybrid-semantic-proof"
SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}$")
ALLOWED_FIELDS = {"visible", "enabled", "label", "role", "kind", "active"}
MAX_JSON = 6 * 1024 * 1024
MAX_IMAGE = 10 * 1024 * 1024


class GuaEvidenceError(ValueError):
    pass


class ToolPort(Protocol):
    def call(self, name: str, arguments: dict[str, Any] | None = None) -> Any: ...


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_json(data: bytes) -> Any:
    if len(data) > MAX_JSON:
        raise GuaEvidenceError("Gua payload too large")
    return json.loads(data)


def _mission(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or type(raw.get("schema_version")) is not int or raw["schema_version"] != 1:
        raise GuaEvidenceError("mission schema_version must be 1")
    mid = raw.get("mission_id")
    if not isinstance(mid, str) or not SAFE_ID.fullmatch(mid) or mid in {".", ".."}:
        raise GuaEvidenceError("unsafe mission_id")
    if raw.get("engine") not in {"godot", "unity"}:
        raise GuaEvidenceError("engine must be godot or unity")
    action = raw.get("action")
    if not isinstance(action, dict) or set(action) != {"tool", "nodeId"}:
        raise GuaEvidenceError("exactly one click_node action required")
    if action["tool"] != "click_node" or not isinstance(action["nodeId"], str) or not action["nodeId"].strip() or len(action["nodeId"]) > 256:
        raise GuaEvidenceError("only a bounded explicit click_node is allowed")
    expectation = raw.get("expected_after")
    if not isinstance(expectation, dict) or set(expectation) != {"tree", "id", "field", "equals"}:
        raise GuaEvidenceError("expected_after requires tree, id, field, equals")
    if expectation["tree"] not in {"ui", "world"}:
        raise GuaEvidenceError("expected tree must be ui/world")
    if not isinstance(expectation["id"], str) or not expectation["id"].strip() or len(expectation["id"]) > 256:
        raise GuaEvidenceError("expected id invalid")
    field = expectation["field"]
    if not isinstance(field, str) or (field not in ALLOWED_FIELDS and not re.fullmatch(r"state\.[a-zA-Z0-9_]{1,64}", field)):
        raise GuaEvidenceError("expected field unsupported")
    if type(expectation["equals"]) not in (str, int, float, bool, type(None)):
        raise GuaEvidenceError("expected value must be primitive")
    return raw


class StdioGuaMcp:
    """Minimal newline JSON-RPC client for an installed gui-mcp executable.

    The game host must already have Gua enabled. This client never installs packages,
    launches an engine, changes observation profiles or authorizes raw game input.
    """
    def __init__(self, executable: str = "gui-mcp", *, bridge_url: str = "ws://127.0.0.1:8765", timeout: float = 12.0):
        if not re.fullmatch(r"ws://(?:127\.0\.0\.1|localhost):[0-9]{1,5}", bridge_url):
            raise GuaEvidenceError("M1.2 permits only local Gua bridges")
        if not 1 <= timeout <= 60:
            raise GuaEvidenceError("timeout must be 1..60 seconds")
        self.timeout = timeout
        self._id = 0
        self._responses: queue.Queue[str | None] = queue.Queue()
        env = dict(os.environ, GUA_BRIDGE_URL=bridge_url)
        self._proc = subprocess.Popen(
            [executable, "mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1, env=env,
        )
        self._reader = threading.Thread(target=self._consume, daemon=True)
        self._reader.start()
        try:
            self._request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "mgsf-gua-bridge", "version": "0.1"}})
            self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            tools = self._request("tools/list", {}).get("tools", [])
            names = {tool.get("name") for tool in tools if isinstance(tool, dict)}
            if not {"get_ui_tree", "get_world_object_tree", "get_screenshot", "click_node"} <= names:
                raise GuaEvidenceError("Gua MCP capabilities missing")
        except Exception:
            self.close()
            raise

    def _consume(self) -> None:
        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            self._responses.put(line[:MAX_JSON + 1])
        self._responses.put(None)

    def _send(self, obj: dict[str, Any]) -> None:
        if not self._proc.stdin:
            raise GuaEvidenceError("MCP stdin closed")
        self._proc.stdin.write(json.dumps(obj, separators=(",", ":")) + "\n")
        self._proc.stdin.flush()

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._id += 1
        request_id = self._id
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        # Each request has its own finite deadline, even for a silent MCP server.
        import time
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise GuaEvidenceError("MCP response timeout")
            try:
                line = self._responses.get(timeout=remaining)
            except queue.Empty as exc:
                raise GuaEvidenceError("MCP response timeout") from exc
            if line is None:
                raise GuaEvidenceError("MCP process exited")
            obj = _read_json(line.encode("utf-8"))
            if not isinstance(obj, dict) or obj.get("id") != request_id:
                # Ignore asynchronous notifications, reject out-of-order responses.
                if isinstance(obj, dict) and "id" not in obj:
                    continue
                raise GuaEvidenceError("unexpected MCP response id")
            if "error" in obj:
                raise GuaEvidenceError("MCP JSON-RPC error")
            if not isinstance(obj.get("result"), dict):
                raise GuaEvidenceError("MCP result malformed")
            return obj["result"]

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        if name not in {"get_ui_tree", "get_world_object_tree", "get_screenshot", "click_node"}:
            raise GuaEvidenceError("tool not allowlisted")
        result = self._request("tools/call", {"name": name, "arguments": arguments or {}})
        if result.get("isError") is True:
            raise GuaEvidenceError("Gua tool returned error")
        content = result.get("content")
        if not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict):
            raise GuaEvidenceError("Gua tool content invalid")
        text = content[0].get("text")
        if not isinstance(text, str):
            raise GuaEvidenceError("Gua tool returned non-text data")
        return _read_json(text.encode("utf-8"))

    def close(self) -> None:
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=2)
        if self._proc.stdin:
            self._proc.stdin.close()

    def __enter__(self) -> "StdioGuaMcp":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


def _snapshot(port: ToolPort, tool: str, collection: str) -> dict[str, Any]:
    value = port.call(tool)
    if not isinstance(value, dict) or not isinstance(value.get(collection), list):
        raise GuaEvidenceError(f"{tool} returned invalid {collection}")
    if len(json.dumps(value, ensure_ascii=False)) > MAX_JSON:
        raise GuaEvidenceError("snapshot too large")
    return value


def _screenshot(port: ToolPort) -> bytes:
    value = port.call("get_screenshot")
    if not isinstance(value, dict) or not isinstance(value.get("dataUri"), str):
        raise GuaEvidenceError("missing Gua screenshot dataUri")
    uri = value["dataUri"]
    if not uri.startswith("data:image/png;base64,"):
        raise GuaEvidenceError("only PNG Gua screenshots supported")
    try:
        blob = base64.b64decode(uri.split(",", 1)[1], validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise GuaEvidenceError("invalid screenshot base64") from exc
    if not 32 <= len(blob) <= MAX_IMAGE or _image(blob) != ".png":
        raise GuaEvidenceError("invalid Gua PNG")
    return blob


def _matches(tree: dict[str, Any], expectation: dict[str, Any]) -> bool:
    key = "nodes" if expectation["tree"] == "ui" else "objects"
    objects = tree.get(key, [])
    matching = [obj for obj in objects if isinstance(obj, dict) and obj.get("id") == expectation["id"]]
    if len(matching) != 1:
        return False
    node = matching[0]
    field = expectation["field"]
    if field.startswith("state."):
        state = node.get("state")
        actual = state.get(field.split(".", 1)[1]) if isinstance(state, dict) else None
    else:
        actual = node.get(field)
    return type(actual) is type(expectation["equals"]) and actual == expectation["equals"]


@dataclass(frozen=True)
class GuaRun:
    root: Path
    evidence_path: Path
    status: str


def run_gua_probe(mission_path: str | Path, port: ToolPort, output_root: str | Path = "evidence",
                  *, evidence_class: str = "deterministic_mock_gua_mcp") -> GuaRun:
    if evidence_class not in {"deterministic_mock_gua_mcp", "recorded_gua_native_mcp"}:
        raise GuaEvidenceError("unknown evidence_class")
    mission_bytes = Path(mission_path).read_bytes()
    mission = _mission(_read_json(mission_bytes))
    root = Path(output_root) / SERVICE / mission["mission_id"] / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=False)
    (root / "mission.json").write_bytes(mission_bytes)
    results: dict[str, Any] = {}
    failure = None
    status = "HOLD"
    try:
        before_ui = _snapshot(port, "get_ui_tree", "nodes")
        before_world = _snapshot(port, "get_world_object_tree", "objects")
        before_png = _screenshot(port)
        results["before_ui"] = before_ui
        results["before_world"] = before_world
        (root / "before.png").write_bytes(before_png)
        action = port.call("click_node", {"nodeId": mission["action"]["nodeId"]})
        # A mere enqueue receipt is not proof of host-side execution.
        completed = (isinstance(action, dict) and action.get("ok") is True
                     and isinstance(action.get("completion"), dict)
                     and action["completion"].get("succeeded") is True)
        results["action_receipt"] = action
        after_ui = _snapshot(port, "get_ui_tree", "nodes")
        after_world = _snapshot(port, "get_world_object_tree", "objects")
        after_png = _screenshot(port)
        results["after_ui"] = after_ui
        results["after_world"] = after_world
        (root / "after.png").write_bytes(after_png)
        same_session = (before_ui.get("sessionEpoch") is not None
                        and before_ui.get("sessionEpoch") == after_ui.get("sessionEpoch"))
        target = after_ui if mission["expected_after"]["tree"] == "ui" else after_world
        semantic_ok = _matches(target, mission["expected_after"])
        changed = _hash(before_png) != _hash(after_png)
        results["assessment"] = {
            "action_completion_confirmed": completed,
            "same_ui_session": same_session,
            "expected_semantic_condition": semantic_ok,
            "screenshot_changed": changed,
            "snapshot_and_pixels_not_atomic": True,
        }
        if completed and same_session and semantic_ok and changed:
            status = "HYBRID_EVIDENCE_SUPPORTED"
        elif completed and same_session and semantic_ok:
            status = "SEMANTIC_EVIDENCE_ONLY"
    except Exception as exc:
        failure = f"{type(exc).__name__}: {str(exc)[:180]}"
        status = "ADAPTER_FAILURE"
    for key, value in results.items():
        _write_json(root / (key + ".json"), value)
    record = {
        "schema_version": 1, "service": SERVICE,
        "mission_sha256": _hash(mission_bytes),
        "source": {"evidence_class": evidence_class, "interface": "native_gui_mcp",
                   "engine": mission["engine"], "runtime_provenance_verified": False},
        "result": {"status": status, "promotion_status": "HOLD",
                   "success_is_not_gameplay_proof": True, "failure": failure},
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
    }
    evidence_path = root / "evaluation.json"
    _write_json(evidence_path, record)
    files = sorted(p for p in root.iterdir() if p.is_file())
    _write_json(root / "manifest.json", {
        "schema_version": 1,
        "artifacts": [{"path": p.name, "bytes": p.stat().st_size, "sha256": _hash(p.read_bytes())} for p in files],
    })
    return GuaRun(root, evidence_path, status)


def verify_gua_evidence(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    valid = False
    try:
        manifest = _read_json((root / "manifest.json").read_bytes())
        record = _read_json((root / "evaluation.json").read_bytes())
        mission_bytes = (root / "mission.json").read_bytes()
        _mission(_read_json(mission_bytes))
        artifacts = manifest["artifacts"]
        seen: set[str] = set()
        valid = (record["schema_version"] == manifest["schema_version"] == 1
                 and record["service"] == SERVICE and record["result"]["promotion_status"] == "HOLD"
                 and record["mission_sha256"] == _hash(mission_bytes))
        for item in artifacts:
            rel = item["path"]
            path = (root / rel).resolve()
            if not isinstance(rel, str) or "/" in rel or "\\" in rel or rel in seen or not path.is_relative_to(root) or not path.is_file():
                valid = False
                break
            seen.add(rel)
            valid &= item["bytes"] == path.stat().st_size and item["sha256"] == _hash(path.read_bytes())
        required = {"evaluation.json", "mission.json"}
        status = record["result"]["status"]
        if status in {"HYBRID_EVIDENCE_SUPPORTED", "SEMANTIC_EVIDENCE_ONLY"}:
            required |= {"before_ui.json", "after_ui.json", "before_world.json", "after_world.json",
                         "before.png", "after.png", "action_receipt.json", "assessment.json"}
            a = _read_json((root / "assessment.json").read_bytes())
            valid &= (a["action_completion_confirmed"] is True and a["same_ui_session"] is True
                      and a["expected_semantic_condition"] is True)
            valid &= (a["screenshot_changed"] is (status == "HYBRID_EVIDENCE_SUPPORTED"))
            before = (root / "before.png").read_bytes()
            after = (root / "after.png").read_bytes()
            valid &= (a["screenshot_changed"] is (_hash(before) != _hash(after)))
            expected = _read_json(mission_bytes)["expected_after"]
            after_tree = _read_json((root / ("after_ui.json" if expected["tree"] == "ui" else "after_world.json")).read_bytes())
            valid &= _matches(after_tree, expected)
        valid &= seen == {p.name for p in root.iterdir() if p.is_file() and p.name != "manifest.json"}
        valid &= required <= seen
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError):
        valid = False
    return {"status": "PASS" if valid else "FAIL", "promotion_status": "HOLD", "artifact_root": str(root)}
