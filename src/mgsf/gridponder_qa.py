"""Evidence-backed GridPonder Python engine QA without vendoring game rules."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Sequence


@dataclass(frozen=True)
class GridPonderQAResult:
    root: Path
    status: str
    passed: int
    failed: int
    skipped: int
    nondeterministic: int


def _revision(root: Path) -> str | None:
    if not (root / ".git").exists():
        return None
    try:
        result = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                                capture_output=True, text=True, timeout=5, check=True)
        sha = result.stdout.strip()
        return sha if re.fullmatch("[0-9a-f]{40}", sha) else None
    except (OSError, subprocess.SubprocessError):
        return None


def _level_files(pack: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in sorted((pack / "levels").glob("*.json")):
        level = json.loads(path.read_text(encoding="utf-8"))
        level_id = level.get("id", path.stem)
        if not isinstance(level_id, str) or not level_id or level_id in result:
            raise ValueError(f"invalid or duplicate level ID: {level_id!r}")
        result[level_id] = path
    return result


def _sequence(pack: Path) -> list[str]:
    game = json.loads((pack / "game.json").read_text(encoding="utf-8"))
    items = game.get("levelSequence")
    if not isinstance(items, list):
        raise ValueError("game.json levelSequence must be an array")
    refs = [entry.get("ref") for entry in items
            if isinstance(entry, dict) and entry.get("type") == "level"]
    if not refs or any(not isinstance(ref, str) or not ref for ref in refs):
        raise ValueError("game.json contains no valid level refs")
    if len(refs) != len(set(refs)):
        raise ValueError("duplicate levelSequence refs")
    return refs


def _worker(root: Path, pack: Path, level: str, timeout: int) -> dict[str, Any]:
    env = os.environ.copy()
    source = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (source, env.get("PYTHONPATH", ""))))
    proc = subprocess.run(
        [sys.executable, "-m", "mgsf._gridponder_worker",
         "--root", str(root), "--pack", str(pack), "--level", level],
        text=True, capture_output=True, check=False, env=env, timeout=timeout,
    )
    if proc.returncode:
        raise RuntimeError(f"upstream worker exit={proc.returncode}: {proc.stderr[-1200:]}")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("upstream worker did not return JSON") from exc
    if not isinstance(result, dict) or result.get("level_id") != level:
        raise ValueError("worker result level mismatch")
    return result


def _assess(a: dict[str, Any], b: dict[str, Any]) -> tuple[str, str]:
    if a != b:
        return "FAIL", "independent state traces diverged"
    if a.get("skipped"):
        return "SKIP", "no solution.goldPath"
    if not a.get("trace"):
        return "FAIL", "no turns replayed"
    if any(not step.get("accepted") for step in a["trace"]):
        return "FAIL", "gold path contains a rejected action"
    if a.get("lost") or not a.get("won"):
        return "FAIL", "gold path did not win"
    return "PASS", "gold path won and independent traces matched"


def run_gridponder_qa(
    pack_dir: str | Path,
    gridponder_root: str | Path,
    output_root: str | Path,
    *,
    levels: Sequence[str] | None = None,
    timeout_seconds: int = 120,
) -> GridPonderQAResult:
    if timeout_seconds < 1:
        raise ValueError("timeout_seconds must be positive")
    root, pack = Path(gridponder_root).resolve(), Path(pack_dir).resolve()
    source = [root / "engines/python/loader.py",
              root / "engines/python/_turn_engine.py",
              root / "engines/python/gold_path.py",
              pack / "manifest.json", pack / "game.json"]
    for path in source:
        if not path.is_file():
            raise FileNotFoundError(f"missing upstream/pack file: {path}")
    referenced = _sequence(pack)
    chosen = list(levels) if levels is not None else referenced
    if not chosen or len(chosen) != len(set(chosen)) or any(x not in referenced for x in chosen):
        raise ValueError("selected levels must be unique members of levelSequence")
    files = _level_files(pack)
    absent = [level for level in chosen if level not in files]
    if absent:
        raise ValueError(f"missing level files: {absent}")
    source += [files[level] for level in chosen]
    hashes = [{"path": str(p), "sha256": sha256(p.read_bytes()).hexdigest()} for p in source]

    reports = []
    for level in chosen:
        try:
            first = _worker(root, pack, level, timeout_seconds)
            second = _worker(root, pack, level, timeout_seconds)
            status, reason = _assess(first, second)
            reports.append({"level_id": level, "status": status, "reason": reason,
                            "run_a": first, "run_b": second})
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            reports.append({"level_id": level, "status": "FAIL",
                            "reason": f"{type(exc).__name__}: {exc}", "run_a": None, "run_b": None})

    passed = sum(x["status"] == "PASS" for x in reports)
    failed = sum(x["status"] == "FAIL" for x in reports)
    skipped = sum(x["status"] == "SKIP" for x in reports)
    nondeterministic = sum("diverged" in x["reason"] for x in reports)
    status = "FAIL" if failed else "HOLD" if skipped else "PASS"
    safe_name = re.sub("[^a-zA-Z0-9_-]", "-", pack.name)[:80] or "pack"
    evidence_dir = Path(output_root) / "gridponder" / safe_name
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence = {
        "schema_version": 1,
        "service": "gridponder-deterministic-qa",
        "evidence_class": "gridponder_python_engine_gold_path_replay",
        "gridponder_revision": _revision(root),
        "pack_dir": str(pack), "gridponder_root": str(root),
        "source_sha256": hashes,
        "status": status,
        "summary": {"selected": len(chosen), "passed": passed, "failed": failed,
                    "skipped": skipped, "nondeterministic": nondeterministic},
        "levels": reports,
        "provenance": {"engine": "upstream GridPonder Python TurnEngine",
                       "independent_worker_processes_per_level": 2,
                       "is_visual_capture": False,
                       "is_dart_parity_proof": False,
                       "is_human_playtest": False},
        "promotion_gate": {"status": "HOLD",
                           "reason": "gold-path QA alone does not prove Dart parity or real-game dogfood"},
    }
    (evidence_dir / "evaluation.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return GridPonderQAResult(evidence_dir, status, passed, failed, skipped, nondeterministic)
