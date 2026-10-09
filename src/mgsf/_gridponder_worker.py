"""Run a GridPonder gold path with its authoritative Python engine."""
import argparse
import dataclasses
from hashlib import sha256
import json
from pathlib import Path
import sys


def canonical(value):
    if dataclasses.is_dataclass(value):
        return canonical(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): canonical(v) for k, v in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [canonical(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((canonical(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise TypeError(f"Unsupported state type: {type(value).__name__}")


def snapshot(engine):
    state = engine.state
    data = {
        "state": canonical(state.to_key()),
        "turn_count": state.turn_count,
        "action_count": state.action_count,
        "sequence_indices": canonical(state.sequence_indices),
        "once_fired_rules": canonical(state.once_fired_rules),
        "pending_move": canonical(state.pending_move),
        "is_won": state.is_won,
        "is_lost": state.is_lost,
    }
    return sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def replay(root: Path, pack: Path, level_id: str):
    sys.path.insert(0, str(root.resolve()))
    from engines.python.loader import load_pack
    from engines.python._turn_engine import TurnEngine
    from engines.python.gold_path import gold_path_actions

    game, levels = load_pack(pack)
    if level_id not in levels:
        raise ValueError(f"Level missing: {level_id}")
    actions = gold_path_actions(levels[level_id])
    if not actions:
        return {"level_id": level_id, "skipped": True, "won": False, "trace": []}
    engine = TurnEngine(game, levels[level_id])
    trace = []
    for index, (action, params) in enumerate(actions, start=1):
        if engine.is_won or engine.is_lost:
            break
        result = engine.execute_turn(action, params, save_history=False)
        trace.append({
            "step": index, "action": action, "params": params,
            "accepted": bool(result.accepted), "state_sha256": snapshot(engine),
            "won": bool(engine.is_won), "lost": bool(engine.is_lost),
            "events": len(result.events),
        })
        if not result.accepted:
            break
    return {
        "level_id": level_id, "skipped": False, "gold_length": len(actions),
        "won": bool(engine.is_won), "lost": bool(engine.is_lost),
        "trace": trace, "final_sha256": snapshot(engine),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--level", required=True)
    args = parser.parse_args()
    print(json.dumps(replay(args.root, args.pack, args.level), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
