# ADR-0002: Stream live pose over localhost TCP instead of file polling

**Status:** accepted
**Date:** 2026-06-11
**Deciders:** Ale (alexandremendoncaalvaro), Dean (Corridor Digital)

## Context

The POC's live path writes `live_pose.pkl` via temp-file-plus-`os.replace` and the addon polls the file's mtime on a 0.03 s modal timer. It verifiably worked (20,329 successful loads in the last clean session) but carries structural costs: every pose is loaded twice per mtime change (confirmed in the modal log), latency has a polling floor, the hot path writes to disk ~30 times per second, Windows file locking required a 10x retry loop, and there are no failure states — the POC killed the engine by window title and the UI could not distinguish "engine died" from "no new pose". The PRD budget is 30 FPS with under 100 ms capture-to-viewport latency.

## Decision

We will stream live poses over a localhost TCP socket: the engine bridge is the server, the addon connects with a background client thread, frames are newline-delimited JSON (ADR-0003), and the newest frame overwrites a latest-wins slot consumed by a main-thread timer. The transport sits behind a `PoseStream` port in `core/` so it is swappable without touching domain code. File-based exchange remains for batch and single-capture jobs, where on-disk artifacts are the product.

## Consequences

* Push-based delivery removes the polling floor and the duplicate-load defect; no disk I/O on the live hot path (GUIDELINES.md §5).
* Connection state gives the UI honest lifecycle states: starting, streaming, reconnecting, stopped-with-reason (diagrammed in doc/workflows.md).
* Process teardown becomes PID-based; the taskkill-by-window-title hack dies.
* The addon needs reconnect logic and a connect-timeout path — more code than reading a file.
* A TCP port must be chosen and can collide; the doctor check verifies port availability at install.
* Debugging loses "open the file and look": tooling must log or capture frames instead.

## Alternatives Considered

* Keep file polling — proven in the POC, but carries the duplicate-read, latency, disk-churn, and locking costs forward; rejected against the latency budget.
* ZMQ pub/sub (as the abandoned engine backend used) — robust, but pyzmq would need vendoring into the Blender extension wheel; plain sockets are stdlib on both sides.
* gRPC — codegen and dependency weight far beyond a single local stream.
* stdout pipe from the engine process — fragile interleaving with logging, blocks on console buffering, no reconnect semantics.
