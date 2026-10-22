from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from mgsf.godotenv_bridge import audit_project, prepare_project

FIXTURE = Path("fixtures/godotenv/sample")


def project(tmp_path, pin="4.7.2 no-dotnet\n"):
    game = tmp_path / "game"
    game.mkdir()
    (game / "project.godot").write_text("config_version=5\n")
    if pin is not None:
        (game / ".godotrc").write_text(pin)
    return game


def test_static_hold_and_nonmutating(tmp_path):
    before = {p.name: p.read_bytes() for p in FIXTURE.iterdir()}
    result = audit_project(FIXTURE, tmp_path)
    assert result.status == "HOLD"
    assert result.evidence["pin"]["version"] == "4.7.2"
    assert result.evidence["pin"]["no_dotnet"] is True
    assert result.evidence["commands"][0][-1] == "--no-dotnet"
    assert json.loads(result.evidence_path.read_text())["status"] == "HOLD"
    assert before == {p.name: p.read_bytes() for p in FIXTURE.iterdir()}


def test_missing_pin(tmp_path):
    assert audit_project(project(tmp_path, None)).status == "FAIL"


def test_conflicting_pin(tmp_path):
    game = project(tmp_path)
    (game / "global.json").write_text('{"msbuild-sdks":{"Godot.NET.Sdk":"4.8.0"}}')
    assert "conflicting" in audit_project(game).evidence["errors"][0]


def test_csproj_support(tmp_path):
    game = project(tmp_path, None)
    (game / "game.csproj").write_text('<Project Sdk="Godot.NET.Sdk/4.7.2"/>')
    assert audit_project(game).evidence["pin"]["no_dotnet"] is False


def test_jsonc_preserves_urls_and_trailing_commas(tmp_path):
    game = project(tmp_path)
    (game / "addons.jsonc").write_text(
        '{"addons":{"demo":{"url":"https://github.com/a/b.git",'
        '"checkout":"' + "a" * 40 + '","subfolder":"addons/demo",},}, // note\n}'
    )
    result = audit_project(game)
    assert result.status == "HOLD"
    assert result.evidence["addons"][0]["checkout"] == "a" * 40


@pytest.mark.parametrize("manifest", [
    '{"addons":{"x":{"url":"https://github.com/a/b","checkout":"main"}}}',
    '{"addons":{"x":{"url":"https://evil.test/a/b","checkout":"' + "a" * 40 + '"}}}',
    '{"addons":{"x":{"url":"https://github.com/a/b","checkout":"' + "a" * 40 + '","subfolder":"../escape"}}}',
    '{"addons":{"x":{"url":"../local","source":"symlink"}}}',
    '{"addons":{"x":{"url":"https://github.com/a/b.zip","source":"zip"}}}',
    '{"addons":{},"path":"../outside"}',
])
def test_unsafe_addons(tmp_path, manifest):
    game = project(tmp_path)
    (game / "addons.jsonc").write_text(manifest)
    assert audit_project(game).status == "FAIL"


def test_prepare_requires_explicit_approval(tmp_path, monkeypatch):
    game = project(tmp_path)
    monkeypatch.setattr("mgsf.godotenv_bridge._exec",
                        lambda *args: pytest.fail("must not run"))
    result = prepare_project(game, tmp_path)
    assert result.status == "HOLD"
    assert result.evidence["executed"] == []


def _mock_live(tmp_path, monkeypatch):
    engine = tmp_path / "Godot"
    engine.write_text("fake")
    monkeypatch.setattr("mgsf.godotenv_bridge.shutil.which",
                        lambda _: "/opt/godotenv")
    commands = []

    def fake(argv, cwd, timeout):
        commands.append(argv)
        output = (str(engine) if argv[1:] == ["godot", "env", "target"]
                  else "4.7.2.stable.official.abc")
        return subprocess.CompletedProcess(argv, 0, output, "")

    monkeypatch.setattr("mgsf.godotenv_bridge._exec", fake)
    return commands


def test_probe_checks_active_engine(tmp_path, monkeypatch):
    game = project(tmp_path)
    commands = _mock_live(tmp_path, monkeypatch)
    assert audit_project(game, probe=True).status == "PASS"
    assert len(commands) == 2


def test_prepare_executes_consented_pins(tmp_path, monkeypatch):
    game = project(tmp_path)
    commands = _mock_live(tmp_path, monkeypatch)
    assert prepare_project(game, tmp_path, allow_global_switch=True).status == "PASS"
    assert commands[:2] == [
        ["/opt/godotenv", "godot", "install", "4.7.2", "--no-dotnet"],
        ["/opt/godotenv", "godot", "use", "4.7.2", "--no-dotnet"],
    ]


def test_existing_addons_never_overwritten(tmp_path, monkeypatch):
    game = project(tmp_path)
    (game / "addons.json").write_text(
        '{"addons":{"x":{"url":"https://github.com/a/b","checkout":"' + "a" * 40 + '"}}}'
    )
    (game / "addons").mkdir()
    monkeypatch.setattr("mgsf.godotenv_bridge.shutil.which",
                        lambda _: "/opt/godotenv")
    monkeypatch.setattr("mgsf.godotenv_bridge._exec",
                        lambda *args: pytest.fail("must not run"))
    assert prepare_project(game, tmp_path, allow_global_switch=True,
                           install_addons=True).status == "FAIL"
