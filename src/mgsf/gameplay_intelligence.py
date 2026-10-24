"""Offline, provenance-first gameplay mechanic recommendation. No network or engine access."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ALLOWED_ENGINES = {"godot", "littlejs"}
TOKEN = re.compile(r"[a-z0-9][a-z0-9_-]*|[\u3040-\u30ff\u3400-\u9fff]+")


def load_mechanics(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("mechanics"), list):
        raise ValueError("invalid mechanics catalog schema")
    seen: set[str] = set()
    for item in data["mechanics"]:
        if not isinstance(item, dict):
            raise ValueError("mechanic must be an object")
        for key in ("id", "name", "summary", "source_url", "provenance", "tags", "style_tags", "engines"):
            if key not in item:
                raise ValueError(f"missing mechanic field: {key}")
        if not all(isinstance(item[k], str) and item[k].strip() for k in ("id", "name", "summary", "source_url", "provenance")):
            raise ValueError("mechanic text fields must be nonempty strings")
        if item["id"] in seen:
            raise ValueError("duplicate mechanic id")
        seen.add(item["id"])
        if not item["source_url"].startswith(("https://", "http://")):
            raise ValueError("source_url must be an HTTP(S) URL")
        for key in ("tags", "style_tags", "engines"):
            if not isinstance(item[key], list) or not all(isinstance(v, str) and v for v in item[key]):
                raise ValueError(f"{key} must be a list of strings")
        if set(item["engines"]) - ALLOWED_ENGINES:
            raise ValueError("unknown engine")
    return data["mechanics"]


def recommend(query: str, mechanics: list[dict[str, Any]], *, engine: str = "godot", limit: int = 5) -> dict[str, Any]:
    if engine not in ALLOWED_ENGINES or limit < 1 or limit > 50:
        raise ValueError("invalid engine or limit")
    if not query.strip():
        raise ValueError("query must not be empty")
    terms = set(TOKEN.findall(query.lower()))
    results = []
    for item in mechanics:
        if engine not in item["engines"]:
            continue
        tags = {s.lower() for s in item["tags"]}
        document = set(TOKEN.findall((" ".join([item["name"], item["summary"], *item["tags"]])).lower()))
        score = 3 * len(terms & tags) + len(terms & document)
        if score:
            results.append((score, item))
    results.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    return {
        "query": query, "engine": engine, "evidence_class": "curated_design_reference",
        "gate": "HOLD", "requires": ["real_engine_run", "recorded_playtest_evidence", "license_review"],
        "matches": [
            {"id": item["id"], "name": item["name"], "score": score,
             "rationale": item["summary"], "style_tags": item["style_tags"],
             "source_url": item["source_url"], "provenance": item["provenance"],
             "prototype_hint": item.get("prototype_hint", {}).get(engine, "")}
            for score, item in results[:limit]
        ],
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="MGSF Gameplay Mechanics Intelligence Bridge")
    parser.add_argument("query")
    parser.add_argument("--catalog", type=Path, default=Path("data/gameplay-mechanics.seed.json"))
    parser.add_argument("--engine", choices=sorted(ALLOWED_ENGINES), default="godot")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(recommend(args.query, load_mechanics(args.catalog), engine=args.engine, limit=args.limit), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
