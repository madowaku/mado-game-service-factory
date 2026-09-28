from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from .gameplay_capture import run_capture_playtest
from .godot_capture_adapter import GodotCaptureAdapterError, run_godot_capture_adapter

PRODUCT_NAME = "MADO Playtest Evidence"
PRODUCT_VERSION = "0.4.0"


def _find_godot() -> str | None:
    for name in ("godot", "godot4", "Godot", "Godot_v4.7.2-stable_win64.exe"):
        resolved = shutil.which(name)
        if resolved:
            return resolved

    candidates: list[Path] = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    program_files = os.environ.get("ProgramFiles")
    if local_app_data:
        candidates.extend(
            [
                Path(local_app_data) / "Programs" / "Godot" / "Godot.exe",
                Path(local_app_data) / "Godot" / "Godot.exe",
            ]
        )
    if program_files:
        candidates.extend(
            [
                Path(program_files) / "Godot" / "Godot.exe",
                Path(program_files) / "Godot Engine" / "Godot.exe",
            ]
        )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def _sample_capture_dir() -> Path | None:
    executable_dir = Path(sys.executable).resolve().parent
    adjacent = executable_dir / "examples" / "sample-capture"
    if adjacent.is_dir():
        return adjacent

    repo_fixture = Path("examples") / "sample-capture"
    if repo_fixture.is_dir():
        return repo_fixture
    return None


def _print_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _self_check(args: argparse.Namespace) -> int:
    godot = args.godot or _find_godot()
    sample = _sample_capture_dir()
    payload = {
        "product": PRODUCT_NAME,
        "version": PRODUCT_VERSION,
        "platform": sys.platform,
        "executable": str(Path(sys.executable).resolve()),
        "godot": godot,
        "sample_capture": str(sample.resolve()) if sample else None,
        "ready_for_sample": sample is not None,
        "ready_for_godot_capture": godot is not None,
    }
    _print_json(payload)
    return 0 if sample is not None else 1


def _analyze(args: argparse.Namespace) -> int:
    result = run_capture_playtest(args.capture, args.output)
    print(f"Evidence: {result.capture.root}")
    print(f"Report: {result.report_root}")
    print(f"Findings: {result.finding_count}")
    print(f"Status: {result.status}")
    return 0 if result.status == "PASS" else 1


def _demo(args: argparse.Namespace) -> int:
    sample = _sample_capture_dir()
    if sample is None:
        print("Sample capture was not found next to the product executable.", file=sys.stderr)
        return 2
    result = run_capture_playtest(sample, args.output)
    print(f"Sample: {sample}")
    print(f"Report: {result.report_root}")
    print(f"Findings: {result.finding_count}")
    print(f"Status: {result.status}")
    return 0 if result.status == "PASS" else 1


def _godot(args: argparse.Namespace) -> int:
    godot = args.godot or _find_godot()
    if godot is None:
        print(
            "Godot was not found. Pass --godot C:\\path\\to\\Godot.exe.",
            file=sys.stderr,
        )
        return 2
    try:
        result = run_godot_capture_adapter(
            args.project,
            godot,
            args.output,
            scene=args.scene,
            source_head_sha=args.source_sha,
        )
    except GodotCaptureAdapterError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Adapter evidence: {result.root}")
    print(f"Raw capture: {result.raw_capture_root}")
    print(f"Report: {result.capture_playtest.report_root}")
    print(f"Findings: {result.capture_playtest.finding_count}")
    print(f"Status: {result.status}")
    return 0 if result.status == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="mado-playtest",
        description=(
            "Capture gameplay evidence and generate playtest findings that point "
            "back to exact media."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {PRODUCT_VERSION}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    self_check = sub.add_parser(
        "self-check",
        help="Check sample files and discover a local Godot executable",
    )
    self_check.add_argument("--godot", help="optional explicit Godot executable")
    self_check.set_defaults(func=_self_check)

    demo = sub.add_parser(
        "demo",
        help="Analyze the bundled sample capture",
    )
    demo.add_argument(
        "--output",
        type=Path,
        default=Path("mado-evidence"),
        help="output directory",
    )
    demo.set_defaults(func=_demo)

    analyze = sub.add_parser(
        "analyze",
        help="Analyze an existing capture directory",
    )
    analyze.add_argument("capture", type=Path, help="capture directory")
    analyze.add_argument(
        "--output",
        type=Path,
        default=Path("mado-evidence"),
        help="output directory",
    )
    analyze.set_defaults(func=_analyze)

    godot = sub.add_parser(
        "godot",
        help="Run a Godot capture scene and generate an evidence-backed report",
    )
    godot.add_argument("project", type=Path, help="Godot project directory")
    godot.add_argument("--godot", help="Godot executable; auto-detected when omitted")
    godot.add_argument(
        "--scene",
        default="res://scenes/capture/mgsf_c6_capture.tscn",
        help="capture scene inside the project",
    )
    godot.add_argument("--source-sha", help="optional expected source commit SHA")
    godot.add_argument(
        "--output",
        type=Path,
        default=Path("mado-evidence"),
        help="output directory",
    )
    godot.set_defaults(func=_godot)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
