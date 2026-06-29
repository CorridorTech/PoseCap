import subprocess
import sys
from collections.abc import Sequence

import pytest
from posecap_addon.engine_process import EngineStartupError, start_engine_stream


def test_start_engine_stream_reads_listening_event_and_stops_process() -> None:
    script = (
        "import json, sys, time; "
        "print(json.dumps({'event': 'listening', 'host': '127.0.0.1', 'port': 42321}), "
        "flush=True); "
        "time.sleep(30)"
    )
    engine = start_engine_stream(
        [sys.executable, "-c", script],
        startup_timeout_seconds=2.0,
    )

    try:
        assert engine.endpoint.host == "127.0.0.1"
        assert engine.endpoint.port == 42321
        assert engine.pid > 0
        assert engine.running
    finally:
        engine.stop(timeout_seconds=2.0)

    assert not engine.running


def test_start_engine_stream_timeout_terminates_process() -> None:
    command = [sys.executable, "-c", "import time; time.sleep(30)"]
    processes: list[subprocess.Popen[str]] = []

    def popen(command: Sequence[str]) -> subprocess.Popen[str]:
        process = subprocess.Popen(
            list(command),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
        )
        processes.append(process)
        return process

    with pytest.raises(EngineStartupError, match="timed out waiting"):
        start_engine_stream(command, startup_timeout_seconds=0.1, popen_factory=popen)

    assert len(processes) == 1
    assert processes[0].poll() is not None
