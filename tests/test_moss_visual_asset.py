import hashlib
import json
import struct
import zlib
from pathlib import Path

import pytest
from mgsf.moss_visual_asset import evaluate_visual_asset, plan_visual_asset

FIXTURES = Path("fixtures/moss-visual")


@pytest.mark.parametrize("name", ["title-screen", "store-capsule", "tutorial-panel"])
def test_compilation_is_deterministic_and_inference_is_not_run(tmp_path, name):
    root = plan_visual_asset(FIXTURES / (name + ".json"), tmp_path)
    m = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    p = json.loads((root / "prompt.txt").read_text(encoding="utf-8"))
    assert m["inference_executed"] is False
    assert p["bbox_coord_space"] == "abs_centralized"
    assert p["bbox_format"] == "yxyx"
    assert m["expected_visible_text"] == [x["text"] for x in p["items"] if x["label"] == "text"]
    assert evaluate_visual_asset(root)["status"] == "HOLD"
    with pytest.raises(FileExistsError):
        plan_visual_asset(FIXTURES / (name + ".json"), tmp_path)


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(width=1000),
    lambda d: d["items"][0].update(bbox=[0, 0, 4000, 4000]),
    lambda d: d["items"][1].pop("text"),
    lambda d: d.update(bbox_format="yxyx"),
])
def test_invalid_layout_is_rejected(tmp_path, mutation):
    d = json.loads((FIXTURES / "store-capsule.json").read_text(encoding="utf-8"))
    mutation(d)
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ValueError):
        plan_visual_asset(f, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def chunk(kind, data):
    return (struct.pack(">I", len(data)) + kind + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))


def make_png(w, h):
    scanlines = b"".join(b"\x00" + b"\xff\x00\x00\xff" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(scanlines)) + chunk(b"IEND", b""))


def test_review_gate(tmp_path):
    root = plan_visual_asset(FIXTURES / "store-capsule.json", tmp_path)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    image = tmp_path / "candidate.png"
    image.write_bytes(make_png(1536, 1024))
    assert evaluate_visual_asset(root, image=image)["status"] == "HOLD"
    r = {
        "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "prompt_sha256": manifest["prompt_sha256"],
        "observed_text": manifest["expected_visible_text"],
        "composition_approved": True, "style_consistent": True, "reviewer": "manual-qa",
    }
    f = tmp_path / "review.json"
    f.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    result = evaluate_visual_asset(root, image=image, review=f)
    assert result["status"] == "PASS" and result["generation_verified"] is False
    r["prompt_sha256"] = "0" * 64
    f.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    assert evaluate_visual_asset(root, image=image, review=f)["status"] == "FAIL"
    r["prompt_sha256"] = manifest["prompt_sha256"]
    r["observed_text"] = ["誤字"]
    f.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    assert evaluate_visual_asset(root, image=image, review=f)["status"] == "HOLD"


def test_png_dimensions_crc_and_plan_hash(tmp_path):
    root = plan_visual_asset(FIXTURES / "title-screen.json", tmp_path)
    image = tmp_path / "bad.png"
    image.write_bytes(make_png(32, 32))
    assert evaluate_visual_asset(root, image=image)["status"] == "FAIL"
    corrupted = bytearray(image.read_bytes())
    corrupted[30] ^= 1
    image.write_bytes(corrupted)
    assert evaluate_visual_asset(root, image=image)["status"] == "FAIL"
    (root / "prompt.txt").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        evaluate_visual_asset(root)
