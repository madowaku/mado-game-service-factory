from pathlib import Path
import json

from mgsf.transport_probe import ProbeSample, run_fixture, summarize


def test_summary_tracks_packets_per_second_and_jitter() -> None:
    samples = [
        ProbeSample("udp", 128, 0, 6),
        ProbeSample("udp", 128, 100, 107),
        ProbeSample("udp", 128, 200, 208),
    ]
    result = summarize(samples)

    assert result.sent_packets == 3
    assert result.delivered_packets == 3
    assert result.loss_rate == 0
    assert result.rtt_min_ms == 6
    assert result.rtt_p50_ms == 7
    assert result.rtt_p95_ms > 7
    assert result.packets_per_second > 0
    assert result.bytes_per_second > 0
    assert result.jitter_ms == 1


def test_fixture_evidence_is_explicitly_not_live(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "samples": [
                    {
                        "transport": "quic-datagram",
                        "payload_bytes": 128,
                        "sent_at_ms": 0,
                        "received_at_ms": 6.1,
                    },
                    {
                        "transport": "quic-datagram",
                        "payload_bytes": 128,
                        "sent_at_ms": 100,
                        "received_at_ms": 106.4,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    evidence_path = run_fixture(fixture, tmp_path / "evidence")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert evidence["real_network_measurement"] is False
    assert evidence["promotion_gate"]["status"] == "HOLD"
    assert evidence["summaries"][0]["transport"] == "quic-datagram"
