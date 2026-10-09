import json
from pathlib import Path

import pytest

from mgsf._gridponder_worker import canonical
from mgsf.gridponder_qa import run_gridponder_qa


def setup_pack(tmp_path: Path):
    upstream = tmp_path / "upstream"
    for filename in ("loader.py", "_turn_engine.py", "gold_path.py"):
        path = upstream / "engines/python" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# stub; mocked worker only\n")
    pack = tmp_path / "carrot_quest"
    (pack / "levels").mkdir(parents=True)
    (pack / "manifest.json").write_text('{"gameId":"carrot_quest"}')
    (pack / "game.json").write_text(json.dumps({
        "levelSequence": [{"type": "story"}, {"type": "level", "ref": "fw_001"}],
    }))
    (pack / "levels/fw_001.json").write_text(json.dumps({
        "id": "fw_001", "solution": {"goldPath": ["right"]},
    }))
    return upstream, pack


def winning():
    return {"level_id": "fw_001", "skipped": False, "won": True, "lost": False,
            "trace": [{"step": 1, "accepted": True, "state_sha256": "aaa"}]}


def test_winning_replay_passes_but_promotion_holds(tmp_path, monkeypatch):
    upstream, pack = setup_pack(tmp_path)
    monkeypatch.setattr("mgsf.gridponder_qa._worker", lambda *args: winning())
    result = run_gridponder_qa(pack, upstream, tmp_path / "out")
    data = json.loads((result.root / "evaluation.json").read_text())
    assert result.status == "PASS"
    assert result.passed == 1
    assert data["promotion_gate"]["status"] == "HOLD"
    assert data["source_sha256"]
    assert data["provenance"]["is_visual_capture"] is False


def test_not_won_fails(tmp_path, monkeypatch):
    upstream, pack = setup_pack(tmp_path)
    monkeypatch.setattr("mgsf.gridponder_qa._worker",
                        lambda *args: {**winning(), "won": False})
    assert run_gridponder_qa(pack, upstream, tmp_path / "out").status == "FAIL"


def test_divergent_replay_fails(tmp_path, monkeypatch):
    upstream, pack = setup_pack(tmp_path)
    variants = iter([winning(), {**winning(), "final_sha256": "changed"}])
    monkeypatch.setattr("mgsf.gridponder_qa._worker", lambda *args: next(variants))
    result = run_gridponder_qa(pack, upstream, tmp_path / "out")
    assert result.status == "FAIL"
    assert result.nondeterministic == 1


def test_absent_gold_path_holds(tmp_path, monkeypatch):
    upstream, pack = setup_pack(tmp_path)
    empty = {"level_id": "fw_001", "skipped": True, "trace": [], "won": False}
    monkeypatch.setattr("mgsf.gridponder_qa._worker", lambda *args: empty)
    assert run_gridponder_qa(pack, upstream, tmp_path / "out").status == "HOLD"


def test_rejected_step_fails(tmp_path, monkeypatch):
    upstream, pack = setup_pack(tmp_path)
    invalid = winning()
    invalid["trace"][0]["accepted"] = False
    monkeypatch.setattr("mgsf.gridponder_qa._worker", lambda *args: invalid)
    assert run_gridponder_qa(pack, upstream, tmp_path / "out").status == "FAIL"


def test_missing_and_unsafe_level_ids_fail_validation(tmp_path):
    upstream, pack = setup_pack(tmp_path)
    with pytest.raises(ValueError, match="levelSequence"):
        run_gridponder_qa(pack, upstream, tmp_path / "out", levels=["../bad"])
    (pack / "levels/fw_001.json").unlink()
    with pytest.raises(ValueError, match="missing level"):
        run_gridponder_qa(pack, upstream, tmp_path / "out")


def test_worker_canonicalization_is_order_stable():
    assert canonical({"b": {3, 1}, "a": {"z": 1, "x": 2}}) == canonical(
        {"a": {"x": 2, "z": 1}, "b": {1, 3}}
    )


def test_worker_runtime_error_is_evidence_failure(tmp_path, monkeypatch):
    upstream, pack = setup_pack(tmp_path)
    def fail(*args):
        raise RuntimeError("engine failed")
    monkeypatch.setattr("mgsf.gridponder_qa._worker", fail)
    result = run_gridponder_qa(pack, upstream, tmp_path / "out")
    assert result.status == "FAIL"
    assert "engine failed" in (result.root / "evaluation.json").read_text()
