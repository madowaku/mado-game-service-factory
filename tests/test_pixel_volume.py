import json
import struct
from pathlib import Path

import pytest

from mgsf.pixel_volume import build_fixture, build_sheet


def test_sheet_dimensions_and_bottom_to_top_order() -> None:
    spec = {"schema_version": 1, "size": [2, 1, 2], "shapes": [
        {"kind": "box", "min": [0, 0, 0], "max": [1, 1, 1], "color": "#ff0000"},
        {"kind": "box", "min": [1, 0, 1], "max": [2, 1, 2], "color": "#00ff00"}]}
    png, manifest = build_sheet(spec)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", png[16:24]) == (4, 1)
    assert manifest["slices"] == 2
    assert manifest["opaque_voxels"] == 2
    assert png == build_sheet(spec)[0]


def test_fixture_creates_provenance_without_claiming_live_engine(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[1] / "fixtures/pixel-volume/toy-car.json"
    manifest_path = build_fixture(fixture, tmp_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert (tmp_path / "toy-car.png").exists()
    assert data["sheet_width"] == data["width"] * data["slices"]
    assert data["engine_render_verified"] is False
    assert data["promotion_gate"] == "HOLD"


@pytest.mark.parametrize("bad", [
    {"schema_version": 1, "size": [0, 2, 2], "shapes": [{}]},
    {"schema_version": 1, "size": [2, 2, 2], "shapes": [{"kind": "box", "min": [0,0,0], "max": [3,2,2], "color": "#ff0000"}]},
    {"schema_version": 1, "size": [2, 2, 2], "shapes": [{"kind": "box", "min": [0,0,0], "max": [2,2,2], "color": "invalid"}]},
])
def test_invalid_specs_fail_closed(bad: dict) -> None:
    with pytest.raises(ValueError):
        build_sheet(bad)
