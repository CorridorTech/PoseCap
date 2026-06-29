"""TCP client for the engine's newline-delimited pose stream."""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from queue import Empty, Queue
from typing import Literal

from posecap_contracts import PoseFrame, decode_pose_frame

ErrorCallback = Callable[[BaseException], None]
ConnectionState = Literal["STOPPED", "CONNECTING", "CONNECTED", "RECONNECTING"]


class TcpPoseStreamClient:
    """Read pose frames on a daemon thread and expose latest-wins semantics."""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        connect_timeout_seconds: float = 5.0,
        retry_interval_seconds: float = 0.05,
        on_error: ErrorCallback | None = None,
    ) -> None:
        if connect_timeout_seconds <= 0:
            raise ValueError("connect_timeout_seconds must be positive")
        if retry_interval_seconds <= 0:
            raise ValueError("retry_interval_seconds must be positive")
        self._host = host
        self._port = port
        self._connect_timeout_seconds = connect_timeout_seconds
        self._retry_interval_seconds = retry_interval_seconds
        self._on_error = on_error
        self._latest: Queue[PoseFrame] = Queue(maxsize=1)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._socket: socket.socket | None = None
        self._error: BaseException | None = None
        self._connection_state: ConnectionState = "STOPPED"

    @property
    def error(self) -> BaseException | None:
        """Return the terminal background-thread error, if any."""
        return self._error

    @property
    def connection_state(self) -> ConnectionState:
        """Return the current background connection state."""
        return self._connection_state

    def start(self) -> None:
        """Start the background reader thread once."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._connection_state = "CONNECTING"
        self._thread = threading.Thread(
            target=self._run,
            name="posecap-tcp-pose-stream",
            daemon=True,
        )
        self._thread.start()

    def latest(self) -> PoseFrame | None:
        """Return the newest unconsumed frame without blocking."""
        try:
            return self._latest.get_nowait()
        except Empty:
            return None

    def close(self, *, timeout_seconds: float = 2.0) -> None:
        """Stop the background reader and close the socket."""
        self._stop.set()
        connection = self._socket
        if connection is not None:
            with suppress(OSError):
                connection.shutdown(socket.SHUT_RDWR)
            connection.close()
        if self._thread is not None:
            self._thread.join(timeout=timeout_seconds)
        self._connection_state = "STOPPED"

    def _run(self) -> None:
        had_connection = False
        try:
            while not self._stop.is_set():
                self._connection_state = "RECONNECTING" if had_connection else "CONNECTING"
                connection = self._connect()
                if connection is None:
                    return
                self._socket = connection
                self._connection_state = "CONNECTED"
                try:
                    self._read_frames(connection)
                finally:
                    self._socket = None
                had_connection = True
        except BaseException as exc:
            self._report_error(exc)
        finally:
            self._socket = None
            if self._stop.is_set():
                self._connection_state = "STOPPED"

    def _connect(self) -> socket.socket | None:
        deadline = time.monotonic() + self._connect_timeout_seconds
        last_error: OSError | None = None
        while not self._stop.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                message = f"timed out connecting to pose stream at {self._host}:{self._port}"
                self._report_error(TimeoutError(message))
                return None
            try:
                timeout = min(self._retry_interval_seconds, remaining)
                return socket.create_connection((self._host, self._port), timeout=timeout)
            except OSError as exc:
                last_error = exc
                self._stop.wait(min(self._retry_interval_seconds, max(0.0, remaining)))
        if not self._stop.is_set() and last_error is not None:
            self._report_error(last_error)
        return None

    def _read_frames(self, connection: socket.socket) -> None:
        connection.settimeout(None)
        with connection, connection.makefile("r", encoding="utf-8") as reader:
            while not self._stop.is_set():
                try:
                    line = reader.readline()
                except OSError:
                    return
                if line == "":
                    return
                self._put_latest(decode_pose_frame(line))

    def _put_latest(self, frame: PoseFrame) -> None:
        while True:
            try:
                self._latest.get_nowait()
            except Empty:
                break
        self._latest.put_nowait(frame)

    def _report_error(self, error: BaseException) -> None:
        self._error = error
        self._connection_state = "STOPPED"
        if self._on_error is None:
            return
        self._on_error(error)
