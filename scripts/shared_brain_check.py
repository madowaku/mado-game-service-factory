"""Offline-only MGSF Shared Brain M0.1 validation; never calls a network service."""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys
import tomllib

ENDPOINT = "https://mcp.notion.com/mcp"
KINDS = {"decision", "finding", "handoff", "skill", "project"}
STATUSES = {"proposed", "approved", "verified", "superseded", "rejected"}
CONFIDENCES = {"unverified", "partial", "verified"}
REQUIRED = {
    "id", "kind", "title", "project", "status", "confidence", "owner",
    "created_at", "summary", "source_refs", "evidence_refs",
    "supersedes", "tags", "visibility", "publish_approved",
}
SENSITIVE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{20,}|ntn_[A-Za-z0-9]{20,}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|"
    r"(?:api[_-]?key|access[_-]?token|password)\s*[:=]\s*[^\s\"']{8,})",
    re.IGNORECASE,
)


def validate(root: Path) -> list[str]:
    problems: list[str] = []
    try:
        codex = tomllib.loads((root / ".codex/config.toml").read_text("utf-8"))
        actual = codex["mcp_servers"]["notion"]["url"]
        if actual != ENDPOINT:
            problems.append("Codex MCP URL must match Notion official endpoint")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        problems.append(f"Codex config invalid: {exc}")

    try:
        raw_config = (root / ".mcp.json").read_text("utf-8")
        claude = json.loads(raw_config)
        notion = claude["mcpServers"]["notion"]
        if notion["url"] != ENDPOINT or notion.get("type") != "http":
            problems.append("Claude project MCP config must use Notion Streamable HTTP")
        if SENSITIVE.search(raw_config):
            problems.append("MCP config may contain a credential")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        problems.append(f"Claude config invalid: {exc}")

    try:
        raw_seed = (root / "shared-brain/seed.json").read_text("utf-8")
        seed = json.loads(raw_seed)
        if SENSITIVE.search(raw_seed):
            problems.append("Seed appears to contain a secret")
        if seed.get("schema_version") != "mgsf.shared-brain.v0.1":
            problems.append("Unexpected seed schema_version")
        records = seed.get("records")
        if not isinstance(records, list) or not records:
            return problems + ["seed records must be a nonempty list"]

        seen: set[str] = set()
        for index, record in enumerate(records):
            tag = f"record[{index}]"
            if not isinstance(record, dict):
                problems.append(f"{tag} must be an object")
                continue
            missing = REQUIRED - record.keys()
            if missing:
                problems.append(f"{tag} missing: {', '.join(sorted(missing))}")
                continue
            if not isinstance(record["id"], str) or not record["id"].strip():
                problems.append(f"{tag} missing stable id")
            if record["id"] in seen:
                problems.append(f"{tag} duplicate id: {record['id']}")
            seen.add(record["id"])
            for key, valid in (("kind", KINDS), ("status", STATUSES), ("confidence", CONFIDENCES)):
                if record[key] not in valid:
                    problems.append(f"{tag} invalid {key}")
            if record["visibility"] not in ("internal", "public"):
                problems.append(f"{tag} invalid visibility")
            if type(record["publish_approved"]) is not bool:
                problems.append(f"{tag} publish_approved must be boolean")
            for key in ("title", "project", "owner", "summary"):
                if not isinstance(record[key], str) or not record[key].strip():
                    problems.append(f"{tag} {key} must be nonempty")
            for key in ("source_refs", "evidence_refs", "supersedes", "tags"):
                if not isinstance(record[key], list) or not all(isinstance(s, str) and s.strip() for s in record[key]):
                    problems.append(f"{tag} {key} must be a list of nonempty strings")
            try:
                date.fromisoformat(record["created_at"])
            except (ValueError, TypeError):
                problems.append(f"{tag} created_at must be an ISO date")
            if record["status"] == "verified" and (record["confidence"] != "verified" or not record["evidence_refs"]):
                problems.append(f"{tag} verified status requires verified confidence and evidence_refs")
            if record["confidence"] == "verified" and not record["evidence_refs"]:
                problems.append(f"{tag} verified confidence requires evidence_refs")
            if record["publish_approved"] and record["visibility"] != "public":
                problems.append(f"{tag} publish_approved requires public visibility")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        problems.append(f"Seed invalid: {exc}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    problems = validate(args.root)
    if problems:
        for problem in problems:
            print("FAIL:", problem, file=sys.stderr)
        return 1
    print("PASS: MGSF Shared Brain M0.1 offline config + seed contract")
    print("NOT RUN: Notion OAuth, MCP read/write, cross-agent handoff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
