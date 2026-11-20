"""Offline, review-first mission compiler for Ava Studio launch-film handoffs.

This module never installs plugins, calls MCP tools, spends credits or renders media.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

BRIEF_SCHEMA = "mgsf.launch-cinema-brief.v1"
MISSION_SCHEMA = "mgsf.launch-cinema-mission.v1"
UPSTREAM_REPOSITORY = "hologramxyz/avastudio-mcp"
UPSTREAM_REVISION = "272410c0a42318b3a0cd85e025e8ed5856637b04"
RATIOS = {"16:9", "9:16", "4:5", "1:1"}


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    return value.strip()


def _public_url(value: object, field: str) -> str:
    value = _text(value, field)
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError(f"{field} must be an HTTP(S) URL without credentials")
    return value


def load_brief(path: Path) -> dict:
    """Validate a small film brief without touching the product or Ava account."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != BRIEF_SCHEMA:
        raise ValueError(f"schema must be {BRIEF_SCHEMA}")
    mission_id = _text(data.get("id"), "id")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", mission_id):
        raise ValueError("id must be a simple lowercase slug")
    _text(data.get("project_repository"), "project_repository")
    for field in ("goal", "audience", "creative_direction", "cta"):
        _text(data.get(field), field)
    if data.get("product_url") is not None:
        _public_url(data["product_url"], "product_url")
    if data.get("aspect_ratio") not in RATIOS:
        raise ValueError(f"aspect_ratio must be one of {sorted(RATIOS)}")
    duration = data.get("duration_seconds")
    if type(duration) is not int or not 9 <= duration <= 15:
        raise ValueError("duration_seconds must be an integer from 9 to 15 for opening-only M0.1")
    if data.get("mode") != "opening_only":
        raise ValueError("mode must be opening_only")
    if data.get("reference_policy") != "review_before_reuse":
        raise ValueError("reference_policy must be review_before_reuse")
    if type(data.get("ava_credit_limit")) is not int or data["ava_credit_limit"] < 0:
        raise ValueError("ava_credit_limit must be a nonnegative integer")
    must_keep = data.get("must_keep")
    if not isinstance(must_keep, list) or not must_keep or any(not isinstance(x, str) or not x.strip() for x in must_keep):
        raise ValueError("must_keep must be a nonempty list of text")
    if data.get("reference_url") is not None:
        _public_url(data["reference_url"], "reference_url")
    if data.get("publication_approved") is not False:
        raise ValueError("M0.1 never pre-approves publication")
    return data


def create_mission_pack(brief_path: Path, output_root: Path) -> Path:
    """Compile a deterministic offline handoff. Never run Ava or Codex here."""
    brief = load_brief(brief_path)
    encoded = json.dumps(brief, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    root = output_root / brief["id"]
    root.mkdir(parents=True, exist_ok=True)
    mission = {
        "schema": MISSION_SCHEMA,
        "id": brief["id"],
        "brief_sha256": digest,
        "upstream": {"repository": UPSTREAM_REPOSITORY, "revision": UPSTREAM_REVISION},
        "brief": brief,
        "status": "NOT_EXECUTED",
        "gate": "HOLD",
        "render_verified": False,
        "release_approved": False,
    }
    (root / "mission.json").write_text(
        json.dumps(mission, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    product_url = brief.get("product_url") or "UNCONFIRMED: operator must supply a live, authorized product URL"
    ref_url = brief.get("reference_url") or "Search Ava's library and review references before selecting one"
    prompt = f"""# MGSF Launch Cinema handoff: {brief['id']}

**STATE: NOT_EXECUTED / HOLD.** This file does not install or invoke Ava Studio.

## Creative brief

- Product repository: {brief['project_repository']}
- Product URL: {product_url}
- Goal: {brief['goal']}
- Audience: {brief['audience']}
- Format: {brief['aspect_ratio']}, {brief['duration_seconds']} seconds, opening only
- Direction: {brief['creative_direction']}
- CTA: {brief['cta']}
- Reference: {ref_url}
- Budget ceiling: {brief['ava_credit_limit']} Ava credits; **zero spend without explicit authorization**

## Creative constraints

""" + "\n".join(f"- {item}" for item in brief["must_keep"]) + f"""

## Local operator workflow

1. Read AGENTS.md, docs/MGSF_LAUNCH_CINEMA_M0_1.md and the pinned upstream skills/launch-remake/SKILL.md before installing or using third-party code. Never execute third-party setup scripts before review.
2. On an operator-controlled Mac/Linux machine, install the reviewed Ava Studio Codex plugin separately and authenticate with an appropriate scoped account. The plugin is **not** installed by this mission compiler.
3. Confirm an authorized live product page and source assets. Search using launch_style_list, inspect candidates using launch_style_get, and keep the original title, post URL, and any permission restrictions. Do not mistake a viral video's popularity for permission to copy protected material.
4. Choose a reference whose abstract pacing and camera grammar fit actual madowaku media. Create an original shot list, story map and 9–15 s opening. Use real pages and real product claims; do not invent UI, statistics, customer reviews or outcomes.
5. Produce music only after explicit spend and audio-rights clearance. Current limit: {brief['ava_credit_limit']} credits. At 0, use silence or cleared local audio, no Ava paid call.
6. Use the upstream local render/QA workflow only after the setup and rights review. Preserve source URL/revision, reference attribution, original captures, exact script/config versions, render command/log, final MP4 and native project, hashes, and observed check verdicts. Never report a check that did not run.
7. Review at mobile playback size, accessibility/readability, product truth, motion, copyright/attribution and consent before further iteration.
8. **Do not post, deploy, upload private files, or promote to active.** Keep the output HOLD until an independently reviewed live video and explicit publication approval exist.

**Evidence expected:** source manifest; rights/attribution register; shot/story map; render project; output MP4; SHA-256 hashes; execution/QA logs; manual review decision.

This is an operator handoff, not a claim that Ava rendered a film.
"""
    (root / "AGENT_PROMPT.md").write_text(prompt, encoding="utf-8")
    return root
