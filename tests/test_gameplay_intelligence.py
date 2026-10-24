import json
from pathlib import Path

import pytest

from mgsf.gameplay_intelligence import load_mechanics, recommend

SEED = Path("data/gameplay-mechanics.seed.json")


def test_seed_and_ranked_recommendation():
    items = load_mechanics(SEED)
    result = recommend("stealth disguise", items, engine="godot")
    assert result["matches"][0]["id"] == "disguise-access"
    assert result["gate"] == "HOLD"
    assert result["matches"][0]["source_url"].startswith("https://")


def test_japanese_lookup_and_engine_hints():
    items = load_mechanics(SEED)
    result = recommend("自動化", items, engine="littlejs")
    assert result["matches"][0]["id"] == "flow-splitting"
    assert result["matches"][0]["prototype_hint"]


def test_no_hallucinated_matches():
    assert recommend("zzzz_nomatch", load_mechanics(SEED))["matches"] == []


def test_catalog_guards(tmp_path):
    data = json.loads(SEED.read_text(encoding="utf-8"))
    data["mechanics"].append(dict(data["mechanics"][0]))
    p = tmp_path / "data.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_mechanics(p)
    with pytest.raises(ValueError, match="invalid engine"):
        recommend("stealth", [], engine="unity")
    with pytest.raises(ValueError, match="query"):
        recommend("  ", [])
