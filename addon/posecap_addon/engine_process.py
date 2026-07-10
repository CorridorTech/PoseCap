"""Engine process launcher for the Blender addon."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from threading import Thread


class EngineStartupError(RuntimeError):
    """Raised when the engine process does not announce a stream endpoint."""


@dataclass(frozen=True)
class EngineEndpoint:
    """TCP endpoint announced by the engine process."""

    host: str
    port: int


@dataclass(frozen=True)
class EngineProcess:
    """Long-running engine process plus its announced TCP endpoint."""

    process: subprocess.Popen[str]
    endpoint: EngineEndpoint
    command: tuple[str, ...]

    @property
    def pid(self) -> int:
        """Return the operating-system process id."""
        return int(self.process.pid)

    @property
    def running(self) -> bool:
        """Return whether the engine process is still running."""
        return self.process.poll() is None

    def stop(self, *, timeout_seconds: float = 5.0) -> None:
        """Terminate the engine by process handle, escalating to kill on timeout."""
        _terminate_process(self.process, timeout_seconds=timeout_seconds)


PopenFactory = Callable[[Sequence[str]], subprocess.Popen[str]]


def start_engine_stream(
    command: Sequence[str],
    *,
    startup_timeout_seconds: float = 5.0,
    popen_factory: PopenFactory | None = None,
) -> EngineProcess:
    """Start an engine process and return its announced TCP stream endpoint."""
    if startup_timeout_seconds <= 0:
        raise ValueError("startup_timeout_seconds must be positive")
    if len(command) == 0:
        raise ValueError("command must not be empty")

    command_tuple = tuple(str(part) for part in command)
    process = (popen_factory or _popen)(command_tuple)
    try:
        line = _read_startup_line(process, timeout_seconds=startup_timeout_seconds)
        endpoint = _parse_listening_event(line)
    except Exception:
        _terminate_process(process, timeout_seconds=1.0)
        raise
    return EngineProcess(process=process, endpoint=endpoint, command=command_tuple)


def _popen(command: Sequence[str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        list(command),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
        env=_sanitized_environment(command),
    )


def _sanitized_environment(command: Sequence[str]) -> dict[str, str]:
    """Child environment with a minimal PATH.

    The host application's PATH (Blender's) poisons OpenCV's video-demuxer
    DLL resolution inside the engine child — the capture then returns the
    first video frame forever (2026-07-10 diagnosis). Every other variable
    is inherited; the executable itself is resolved with the parent's PATH
    before this environment applies.
    """
    environment = dict(os.environ)
    entries: list[str] = []
    executable_dir = str(Path(command[0]).parent)
    if executable_dir not in ("", "."):
        entries.append(executable_dir)
    # os.environ is case-insensitive on Windows; the plain-dict copy is not.
    system_root = os.environ.get("SYSTEMROOT", "")
    if system_root != "":
        entries.append(str(Path(system_root) / "System32"))
        entries.append(system_root)
    environment["PATH"] = os.pathsep.join(entries)
    return environment


def _read_startup_line(process: subprocess.Popen[str], *, timeout_seconds: float) -> str:
    stdout = process.stdout
    if stdout is None:
        raise EngineStartupError("engine stdout was not captured")

    result: Queue[str | BaseException] = Queue(maxsize=1)
    reader = Thread(
        target=_readline_into_queue,
        args=(stdout, result),
        name="posecap-engine-startup-reader",
        daemon=True,
    )
    reader.start()
    try:
        value = result.get(timeout=timeout_seconds)
    except Empty as exc:
        raise EngineStartupError("timed out waiting for engine stream endpoint") from exc
    if isinstance(value, BaseException):
        raise EngineStartupError("failed to read engine stream endpoint") from value
    if value == "":
        stderr = _read_stderr_if_exited(process)
        message = "engine exited before announcing stream endpoint"
        if stderr != "":
            message = f"{message}: {stderr}"
        raise EngineStartupError(message)
    return value


def _readline_into_queue(stream, result: Queue[str | BaseException]) -> None:
    try:
        result.put(stream.readline())
    except BaseException as exc:
        result.put(exc)


def _read_stderr_if_exited(process: subprocess.Popen[str]) -> str:
    if process.poll() is None or process.stderr is None:
        return ""
    return process.stderr.read().strip()


def _parse_listening_event(line: str) -> EngineEndpoint:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        raise EngineStartupError(f"engine startup line was not JSON: {line.strip()}") from exc
    if not isinstance(payload, dict) or payload.get("event") != "listening":
        raise EngineStartupError(f"engine startup line was not a listening event: {line.strip()}")

    host = payload.get("host")
    port = payload.get("port")
    if not isinstance(host, str) or type(port) is not int:
        raise EngineStartupError(f"engine listening event had invalid host/port: {line.strip()}")
    return EngineEndpoint(host=host, port=port)


def _terminate_process(process: subprocess.Popen[str], *, timeout_seconds: float) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=timeout_seconds)
    _close_process_pipes(process)


def _close_process_pipes(process: subprocess.Popen[str]) -> None:
    for stream in (process.stdout, process.stderr):
        if stream is not None:
            stream.close()
