from __future__ import annotations

import json
from pathlib import Path

from mgsf import product_cli


def test_product_version_is_m0_4() -> None:
    assert product_cli.PRODUCT_VERSION == "0.4.0"


def test_self_check_reports_sample_when_adjacent_layout_exists(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    fake_exe = tmp_path / "mado-playtest.exe"
    fake_exe.write_bytes(b"x")
    sample = tmp_path / "examples" / "sample-capture"
    sample.mkdir(parents=True)

    monkeypatch.setattr(product_cli.sys, "executable", str(fake_exe))
    code = product_cli._self_check(type("Args", (), {"godot": None})())

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ready_for_sample"] is True
    assert payload["version"] == "0.4.0"


def test_demo_uses_bundled_sample_layout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_exe = tmp_path / "mado-playtest.exe"
    fake_exe.write_bytes(b"x")
    sample = tmp_path / "examples" / "sample-capture"
    sample.mkdir(parents=True)

    monkeypatch.setattr(product_cli.sys, "executable", str(fake_exe))

    class FakeResult:
        status = "PASS"
        finding_count = 1
        report_root = tmp_path / "report"

    monkeypatch.setattr(product_cli, "run_capture_playtest", lambda capture, output: FakeResult())
    args = type("Args", (), {"output": tmp_path / "out"})()
    assert product_cli._demo(args) == 0
