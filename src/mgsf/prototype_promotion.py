from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any, Iterable


@dataclass(frozen=True)
class PromotionResult:
    root: Path
    status: str
    selected_engine: str | None
    selected_score: float | None


def _load_evidence(path: str | Path) -> dict[str, Any]:
    candidate = Path(path)
    if candidate.is_dir():
        candidate = candidate / "evaluation.json"
    data = json.loads(candidate.read_text(encoding="utf-8"))
    data["_path"] = str(candidate)
    return data


def promote_prototype(
    evidence_paths: Iterable[str | Path],
    output_root: str | Path,
    *,
    engine: str = "edenspark",
) -> PromotionResult:
    evidence = [_load_evidence(path) for path in evidence_paths]
    if not evidence:
        raise ValueError("at least one evidence bundle is required")

    live = [item for item in evidence if item.get("evidence_class") != "deterministic_edenspark_fixture"]
    passing = [item for item in live if item.get("status") == "PASS"]
    passing.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)

    if passing:
        chosen = passing[0]
        status = "PROMOTE"
        reason = "at least one recorded live agent run passed the prototype evidence contract"
        score = float(chosen.get("score", 0.0))
    elif live:
        chosen = max(live, key=lambda item: float(item.get("score", 0.0)))
        status = "ITERATE"
        reason = "live attempts exist but none satisfy the promotion contract"
        score = float(chosen.get("score", 0.0))
    else:
        chosen = max(evidence, key=lambda item: float(item.get("score", 0.0)))
        status = "HOLD"
        reason = "fixture-only evidence is insufficient for promotion"
        score = float(chosen.get("score", 0.0))

    mission_id = str(chosen.get("mission_id", "prototype"))
    root = Path(output_root) / mission_id
    root.mkdir(parents=True, exist_ok=True)
    decision = {
        "schema_version": 1,
        "service": "prototype-promotion-gate",
        "mission_id": mission_id,
        "status": status,
        "reason": reason,
        "selected_engine": engine if status == "PROMOTE" else None,
        "selected_score": round(score, 4),
        "selected_evidence": chosen.get("_path"),
        "candidate_count": len(evidence),
        "live_candidate_count": len(live),
        "pass_candidate_count": len(passing),
    }
    (root / "promotion-decision.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
    return PromotionResult(
        root=root,
        status=status,
        selected_engine=engine if status == "PROMOTE" else None,
        selected_score=score,
    )
