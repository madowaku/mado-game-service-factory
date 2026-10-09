from __future__ import annotations

import argparse
from pathlib import Path

from .catalog import load_catalog
from .edenspark_agent_adapter import (
    create_mission_pack,
    evaluate_result as evaluate_edenspark_result,
    load_mission as load_edenspark_mission,
    run_autonomous_loop as run_edenspark_loop,
)
from .gameplay_capture import run_capture_playtest, run_gameplay_capture
from .godot_capture_adapter import run_godot_capture_adapter
from .playtest_report import run_playtest_report
from .unity_cli_harness import run_unity_harness
from .prototype_promotion import promote_prototype
from .real_game_bridge import run_real_game_bridge, run_real_game_dogfood
from .transport_probe import run_fixture as run_transport_fixture


def _catalog_path(value: str | None) -> Path:
    return Path(value or "catalog/services.yaml")


def main() -> int:
    parser = argparse.ArgumentParser(prog="mgsf")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-catalog", help="Validate the service catalog")
    validate.add_argument("--path")

    listing = sub.add_parser("list", help="List services")
    listing.add_argument("--path")
    listing.add_argument("--stage")

    playtest = sub.add_parser(
        "playtest-report",
        help="Turn an MGEL M0 Evidence Bundle into an actionable playtest report",
    )
    playtest.add_argument("bundle", type=Path, help="MGEL Evidence Bundle directory")
    playtest.add_argument(
        "--output-root",
        type=Path,
        default=Path("evidence"),
        help="root directory for the service Evidence Bundle",
    )

    capture = sub.add_parser(
        "gameplay-capture",
        help="Package gameplay media and timeline into integrity-checked evidence",
    )
    capture.add_argument(
        "capture_root",
        type=Path,
        help="capture directory containing capture.json, timeline.jsonl, and media",
    )
    capture.add_argument(
        "--output-root",
        type=Path,
        default=Path("evidence"),
        help="root directory for gameplay capture evidence",
    )

    capture_report = sub.add_parser(
        "capture-playtest-report",
        help="Package gameplay capture evidence and turn captured friction into a playtest report",
    )
    capture_report.add_argument(
        "capture_root",
        type=Path,
        help="capture directory containing capture.json, timeline.jsonl, and media",
    )
    capture_report.add_argument(
        "--output-root",
        type=Path,
        default=Path("evidence"),
        help="root directory for capture and report evidence",
    )

    godot_capture = sub.add_parser(
        "godot-capture",
        help="Run a Godot capture scene and feed direct gameplay media into MGSF",
    )
    godot_capture.add_argument("project", type=Path, help="Godot project directory")
    godot_capture.add_argument(
        "--godot",
        required=True,
        help="Godot executable path or command",
    )
    godot_capture.add_argument(
        "--scene",
        default="res://scenes/capture/mgsf_c6_capture.tscn",
        help="capture scene inside the target Godot project",
    )
    godot_capture.add_argument(
        "--source-sha",
        help="expected source commit SHA; defaults to git rev-parse HEAD",
    )
    godot_capture.add_argument(
        "--xvfb",
        action="store_true",
        help="run Godot through xvfb-run -a on Linux",
    )
    godot_capture.add_argument(
        "--output-root",
        type=Path,
        default=Path("evidence"),
        help="root directory for direct capture evidence",
    )

    bridge = sub.add_parser(
        "real-game-bridge",
        help="Bridge recorded real-project headless evidence into an MGEL bundle",
    )
    bridge.add_argument("record", type=Path, help="recorded real-game contract JSON")
    bridge.add_argument("runtime_log", type=Path, help="recorded runtime log")
    bridge.add_argument(
        "--output-root",
        type=Path,
        default=Path("evidence"),
        help="root directory for bridge evidence",
    )

    dogfood = sub.add_parser(
        "dogfood-playtest-report",
        help="Run real-game bridge and feed the result into playtest-report",
    )
    dogfood.add_argument("record", type=Path, help="recorded real-game contract JSON")
    dogfood.add_argument("runtime_log", type=Path, help="recorded runtime log")
    dogfood.add_argument(
        "--output-root",
        type=Path,
        default=Path("evidence"),
        help="root directory for bridge and service evidence",
    )

    transport_probe = sub.add_parser(
        "transport-probe",
        help="Compile deterministic transport observations into network evidence",
    )
    transport_probe.add_argument("fixture", type=Path, help="transport fixture JSON")
    transport_probe.add_argument(
        "--output-root",
        type=Path,
        default=Path("evidence/transport-probe"),
        help="output directory for transport evidence",
    )

    edenspark_plan = sub.add_parser(
        "edenspark-plan",
        help="Compile a game hypothesis into an EdenSpark/Codex mission pack",
    )
    edenspark_plan.add_argument("mission", type=Path, help="mission JSON")
    edenspark_plan.add_argument(
        "--output-root",
        type=Path,
        default=Path("missions/edenspark"),
        help="root directory for generated mission packs",
    )

    edenspark_eval = sub.add_parser(
        "edenspark-eval",
        help="Evaluate structured EdenSpark agent evidence without trusting agent self-report",
    )
    edenspark_eval.add_argument("project", type=Path, help="EdenSpark project directory")
    edenspark_eval.add_argument("mission", type=Path, help="mission JSON")
    edenspark_eval.add_argument("result", type=Path, help="structured agent result JSON")
    edenspark_eval.add_argument(
        "--runner-record",
        type=Path,
        help="MGSF codex-exec runner.json for live evidence",
    )
    edenspark_eval.add_argument(
        "--fixture",
        action="store_true",
        help="mark this evaluation deterministic fixture evidence; fixture evidence always HOLDs",
    )
    edenspark_eval.add_argument(
        "--output-root",
        type=Path,
        default=Path("evidence/edenspark"),
        help="root directory for EdenSpark evaluation evidence",
    )

    edenspark_loop = sub.add_parser(
        "edenspark-loop",
        help="Run Codex against a project-provided EdenSpark MCP and iterate until PASS or budget exhaustion",
    )
    edenspark_loop.add_argument("project", type=Path, help="EdenSpark project directory")
    edenspark_loop.add_argument("mission", type=Path, help="mission JSON")
    edenspark_loop.add_argument("--codex", default="codex", help="Codex CLI executable")
    edenspark_loop.add_argument("--max-iterations", type=int)
    edenspark_loop.add_argument("--timeout-seconds", type=int, default=1800)
    edenspark_loop.add_argument(
        "--output-root",
        type=Path,
        default=Path("evidence/edenspark"),
        help="root directory for runner and evaluation evidence",
    )

    promotion = sub.add_parser(
        "prototype-promote",
        help="Promote, iterate, or hold a prototype from one or more evidence bundles",
    )
    promotion.add_argument(
        "evidence",
        nargs="+",
        type=Path,
        help="evaluation.json files or containing directories",
    )
    promotion.add_argument("--engine", default="edenspark")
    promotion.add_argument(
        "--output-root",
        type=Path,
        default=Path("evidence/prototype-promotion"),
        help="root directory for promotion decisions",
    )

    unity_harness = sub.add_parser(
        "unity-harness",
        help="Probe a Unity CLI/Pipeline Editor and optionally capture EditMode NUnit evidence",
    )
    unity_harness.add_argument("project", type=Path, help="Unity project directory")
    unity_harness.add_argument("--unity", default="unity", help="Unity CLI binary or path")
    unity_harness.add_argument("--run-tests", action="store_true", help="explicitly run Unity EditMode tests")
    unity_harness.add_argument("--fixture", type=Path, help="replay a deterministic fixture; always HOLD")
    unity_harness.add_argument("--timeout-seconds", type=int, default=120)
    unity_harness.add_argument("--output-root", type=Path, default=Path("evidence/unity-cli"))

    args = parser.parse_args()

    if args.command == "unity-harness":
        result = run_unity_harness(
            args.project, args.output_root, unity=args.unity,
            run_tests=args.run_tests, timeout_seconds=args.timeout_seconds,
            fixture=args.fixture,
        )
        print(f"Unity CLI evidence: {result.root / 'evaluation.json'}")
        print(f"adapter=unity-cli status={result.status} reason={result.reason}")
        return 0 if result.status in {"PASS", "HOLD"} else 1

    if args.command in {"validate-catalog", "list"}:
        catalog = load_catalog(_catalog_path(args.path))
        if args.command == "validate-catalog":
            print(f"catalog ok: {len(catalog['services'])} services")
            return 0

        services = catalog["services"]
        if args.stage:
            services = [s for s in services if s["stage"] == args.stage]
        for service in services:
            print(f"{service['id']}\t{service['stage']}\t{service['name']}")
        return 0

    if args.command == "transport-probe":
        evidence_path = run_transport_fixture(args.fixture, args.output_root)
        print(f"Transport evidence: {evidence_path}")
        print("service=quic-transport-probe evidence=fixture gate=HOLD")
        return 0

    if args.command == "edenspark-plan":
        root = create_mission_pack(args.mission, args.output_root)
        print(f"EdenSpark mission pack: {root}")
        return 0

    if args.command == "edenspark-eval":
        mission = load_edenspark_mission(args.mission)
        runner = None
        if args.runner_record:
            import json

            runner = json.loads(args.runner_record.read_text(encoding="utf-8"))
        evidence_class = (
            "deterministic_edenspark_fixture"
            if args.fixture
            else "recorded_edenspark_agent_mcp_run"
        )
        result = evaluate_edenspark_result(
            args.project,
            mission,
            args.result,
            args.output_root,
            evidence_class=evidence_class,
            runner_record=runner,
        )
        print(f"EdenSpark evidence: {result.root}")
        print(f"adapter=edenspark status={result.status} score={result.score:.4f}")
        return 0 if result.status in {"PASS", "HOLD"} else 1

    if args.command == "edenspark-loop":
        result = run_edenspark_loop(
            args.project,
            args.mission,
            args.output_root,
            codex=args.codex,
            max_iterations=args.max_iterations,
            timeout_seconds=args.timeout_seconds,
        )
        print(f"EdenSpark loop evidence: {result.root}")
        print(
            f"service=edenspark-autonomous-playtest status={result.status} "
            f"iterations={result.iterations} best_score={result.best_score:.4f}"
        )
        return 0 if result.status == "PASS" else 1

    if args.command == "prototype-promote":
        result = promote_prototype(args.evidence, args.output_root, engine=args.engine)
        print(f"Promotion evidence: {result.root}")
        print(f"service=prototype-promotion-gate status={result.status}")
        return 0 if result.status in {"PROMOTE", "HOLD"} else 1

    if args.command == "playtest-report":
        result = run_playtest_report(args.bundle, args.output_root)
        print(f"Evidence bundle: {result.root}")
        print(
            f"service=playtest-report findings={result.finding_count} "
            f"eval={result.eval_status}"
        )
        return 0 if result.eval_status == "PASS" else 1

    if args.command == "gameplay-capture":
        result = run_gameplay_capture(args.capture_root, args.output_root)
        print(f"Capture evidence: {result.root}")
        print(
            f"service=gameplay-capture media={result.media_count} "
            f"events={result.event_count} eval={result.eval_status}"
        )
        return 0 if result.eval_status == "PASS" else 1

    if args.command == "capture-playtest-report":
        result = run_capture_playtest(args.capture_root, args.output_root)
        print(f"Capture evidence: {result.capture.root}")
        print(f"MGEL bridge: {result.mgel_root}")
        print(f"Playtest report: {result.report_root}")
        print(
            f"capture-playtest findings={result.finding_count} "
            f"eval={result.status}"
        )
        return 0 if result.status == "PASS" else 1

    if args.command == "godot-capture":
        prefix = ["xvfb-run", "-a"] if args.xvfb else []
        result = run_godot_capture_adapter(
            args.project,
            args.godot,
            args.output_root,
            scene=args.scene,
            command_prefix=prefix,
            source_head_sha=args.source_sha,
        )
        print(f"Godot adapter evidence: {result.root}")
        print(f"Raw capture: {result.raw_capture_root}")
        print(f"Playtest report: {result.capture_playtest.report_root}")
        print(
            f"adapter=godot-capture findings={result.capture_playtest.finding_count} "
            f"eval={result.status}"
        )
        return 0 if result.status == "PASS" else 1

    if args.command == "real-game-bridge":
        result = run_real_game_bridge(args.record, args.runtime_log, args.output_root)
        print(f"Bridge evidence: {result.root}")
        print(f"MGEL bundle: {result.mgel_root}")
        print(f"bridge=real-game-bridge eval={result.eval_status}")
        return 0 if result.eval_status == "PASS" else 1

    if args.command == "dogfood-playtest-report":
        result = run_real_game_dogfood(
            args.record,
            args.runtime_log,
            args.output_root,
        )
        print(f"Bridge evidence: {result.bridge.root}")
        print(f"Playtest report: {result.report_root}")
        print(
            f"dogfood=playtest-report findings={result.finding_count} "
            f"eval={result.status}"
        )
        return 0 if result.status == "PASS" else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
