from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import math
import statistics
from typing import Iterable, Sequence


TRANSPORTS = {"udp", "quic-stream", "quic-datagram"}


@dataclass(frozen=True)
class ProbeSample:
    transport: str
    payload_bytes: int
    sent_at_ms: float
    received_at_ms: float
    packet_count: int = 1
    delivered: bool = True

    @property
    def rtt_ms(self) -> float | None:
        if not self.delivered:
            return None
        return max(0.0, self.received_at_ms - self.sent_at_ms)


@dataclass(frozen=True)
class ProbeSummary:
    transport: str
    payload_bytes: int
    sent_packets: int
    delivered_packets: int
    duration_s: float
    packets_per_second: float
    bytes_per_second: float
    loss_rate: float
    rtt_min_ms: float | None
    rtt_p50_ms: float | None
    rtt_p95_ms: float | None
    jitter_ms: float | None

    def as_dict(self) -> dict[str, object]:
        return {
            "transport": self.transport,
            "payload_bytes": self.payload_bytes,
            "sent_packets": self.sent_packets,
            "delivered_packets": self.delivered_packets,
            "duration_s": round(self.duration_s, 6),
            "packets_per_second": round(self.packets_per_second, 6),
            "bytes_per_second": round(self.bytes_per_second, 6),
            "loss_rate": round(self.loss_rate, 6),
            "rtt_ms": {
                "min": _round_or_none(self.rtt_min_ms),
                "p50": _round_or_none(self.rtt_p50_ms),
                "p95": _round_or_none(self.rtt_p95_ms),
            },
            "jitter_ms": _round_or_none(self.jitter_ms),
        }


def _round_or_none(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


def _percentile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def summarize(samples: Iterable[ProbeSample]) -> ProbeSummary:
    rows = list(samples)
    if not rows:
        raise ValueError("at least one probe sample is required")

    transports = {row.transport for row in rows}
    payloads = {row.payload_bytes for row in rows}
    if len(transports) != 1:
        raise ValueError("summary requires one transport")
    if len(payloads) != 1:
        raise ValueError("summary requires one payload size")
    transport = next(iter(transports))
    if transport not in TRANSPORTS:
        raise ValueError(f"unsupported transport: {transport}")

    sent_packets = sum(max(1, row.packet_count) for row in rows)
    delivered_packets = sum(max(1, row.packet_count) for row in rows if row.delivered)
    started = min(row.sent_at_ms for row in rows)
    ended = max(row.received_at_ms if row.delivered else row.sent_at_ms for row in rows)
    duration_s = max((ended - started) / 1000.0, 0.001)
    rtts = [row.rtt_ms for row in rows if row.rtt_ms is not None]
    rtts_float = [float(value) for value in rtts]
    jitter = (
        statistics.mean(abs(b - a) for a, b in zip(rtts_float, rtts_float[1:]))
        if len(rtts_float) >= 2
        else None
    )

    return ProbeSummary(
        transport=transport,
        payload_bytes=next(iter(payloads)),
        sent_packets=sent_packets,
        delivered_packets=delivered_packets,
        duration_s=duration_s,
        packets_per_second=sent_packets / duration_s,
        bytes_per_second=(sent_packets * next(iter(payloads))) / duration_s,
        loss_rate=(sent_packets - delivered_packets) / sent_packets,
        rtt_min_ms=min(rtts_float) if rtts_float else None,
        rtt_p50_ms=_percentile(rtts_float, 0.50),
        rtt_p95_ms=_percentile(rtts_float, 0.95),
        jitter_ms=jitter,
    )


def load_fixture(path: str | Path) -> list[ProbeSample]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("fixture schema_version must be 1")
    samples = []
    for item in data.get("samples", []):
        samples.append(
            ProbeSample(
                transport=item["transport"],
                payload_bytes=int(item["payload_bytes"]),
                sent_at_ms=float(item["sent_at_ms"]),
                received_at_ms=float(item.get("received_at_ms", item["sent_at_ms"])),
                packet_count=int(item.get("packet_count", 1)),
                delivered=bool(item.get("delivered", True)),
            )
        )
    return samples


def run_fixture(path: str | Path, output_root: str | Path) -> Path:
    samples = load_fixture(path)
    grouped: dict[tuple[str, int], list[ProbeSample]] = {}
    for sample in samples:
        grouped.setdefault((sample.transport, sample.payload_bytes), []).append(sample)

    summaries = [
        summarize(grouped[key]).as_dict()
        for key in sorted(grouped)
    ]

    out = Path(output_root)
    out.mkdir(parents=True, exist_ok=True)
    evidence = {
        "schema_version": 1,
        "evidence_class": "deterministic_transport_fixture",
        "real_network_measurement": False,
        "source_fixture": str(Path(path)),
        "summaries": summaries,
        "promotion_gate": {
            "status": "HOLD",
            "reason": "fixture evidence only; live QUIC/UDP adapter evidence is required before promotion",
        },
    }
    target = out / "transport-probe-evidence.json"
    target.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    return target
