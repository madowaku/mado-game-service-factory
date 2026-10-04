# MGSF-M0.5 QUIC Transport Probe / Network Evidence Harness

## Purpose

Turn real-time game networking choices into evidence instead of protocol folklore.

The first milestone does **not** claim that QUIC has been exercised on a live socket. It establishes the measurement contract, deterministic fixture path, and evidence format required before a QUIC adapter may be promoted.

## Why now

The SEGA CEDEC 2025 case study exposed a useful trap: bytes/sec alone can look healthy while packet rate, ACK behavior, jitter, buffering, and migration timing still cause disconnects.

MGSF therefore treats **packet shape** as a first-class artifact.

## M0.5 scope

The harness records:

- transport: UDP / QUIC Stream / QUIC Datagram
- payload bytes
- sent and delivered packet counts
- packets/sec
- bytes/sec
- loss rate
- RTT min / p50 / p95
- mean adjacent RTT delta as a simple jitter signal
- evidence provenance
- promotion gate state

## Evidence classes

### deterministic_transport_fixture

Reconstructed or synthetic observations used to validate calculations and output contracts.

Must always emit:

- `real_network_measurement: false`
- promotion gate: `HOLD`

### live_transport_probe

Reserved for a later adapter that performs actual network I/O.

Promotion to active requires this class plus repeatable evidence.

## CLI boundary

M0.5 core code lives in `src/mgsf/transport_probe.py`.

The next patch should wire:

```
mgsf transport-probe fixtures/network/sega-quic-baseline.json --output-root evidence/quic-probe
```

into the existing CLI after the core contract is accepted.

## Promotion gate

QUIC is not promoted because it is modern or standardized.

A live adapter must demonstrate a useful result against the existing baseline, including:

- p95 RTT or jitter acceptable for the target game
- packet rate explicitly reported
- loss/disconnect behavior reported
- provenance says whether measurements are fixture, loopback, LAN, WAN, or impaired-network
- no fixture is described as a live QUIC result

Connection Migration is outside M0.5 and belongs in a later chaos/migration milestone.

## Roadmap note

The previous README named "External Tester Preview" as MGSF-M0.5. The QUIC evidence harness now takes M0.5 by explicit project decision. External Tester Preview moves to the next unallocated milestone so the two efforts do not silently share an identifier.
