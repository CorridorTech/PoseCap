import socket
import time
from collections.abc import Iterable
from queue import Empty, Queue
from threading import Event, Thread

import pytest
from posecap_addon.stream_client import TcpPoseStreamClient
from posecap_contracts import SCHEMA_VERSION, PoseFrame, PosePayload, encode_pose_frame


def test_tcp_pose_stream_client_keeps_latest_unconsumed_frame() -> None:
    first = PoseFrame(SCHEMA_VERSION, 1, 100.0, "ok", _empty_payload())
    second = PoseFrame(SCHEMA_VERSION, 2, 100.5, "no_person", None)
    server = _FrameServer([first, second])
    server.start()
    client = TcpPoseStreamClient(
        server.host,
        server.port,
        connect_timeout_seconds=1.0,
        retry_interval_seconds=0.01,
    )

    client.start()
    try:
        server.wait_done()

        latest = _next_frame(client, seq=2)
        assert latest == second
        assert client.latest() is None
    finally:
        client.close()
        server.close()


def test_tcp_pose_stream_client_continues_after_idle_gap_between_frames() -> None:
    first = PoseFrame(SCHEMA_VERSION, 1, 100.0, "no_person", None)
    second = PoseFrame(SCHEMA_VERSION, 2, 100.5, "no_person", None)
    server = _FrameServer([first, second], frame_interval_seconds=0.35)
    server.start()
    client = TcpPoseStreamClient(
        server.host,
        server.port,
        connect_timeout_seconds=1.0,
        retry_interval_seconds=0.01,
    )

    client.start()
    try:
        assert _next_frame(client, seq=1) == first
        assert _next_frame(client, seq=2) == second
        assert client.error is None
    finally:
        client.close()
        server.close()


def test_tcp_pose_stream_client_close_during_connect_is_not_reported_as_error() -> None:
    port = _unused_localhost_port()
    errors: Queue[BaseException] = Queue()
    client = TcpPoseStreamClient(
        "127.0.0.1",
        port,
        connect_timeout_seconds=1.0,
        retry_interval_seconds=0.2,
        on_error=errors.put,
    )

    client.start()
    time.sleep(0.05)
    client.close()

    assert client.error is None
    with pytest.raises(Empty):
        errors.get_nowait()


def test_tcp_pose_stream_client_reconnects_after_socket_drop() -> None:
    first = PoseFrame(SCHEMA_VERSION, 1, 100.0, "no_person", None)
    second = PoseFrame(SCHEMA_VERSION, 2, 100.5, "no_person", None)
    server = _ReconnectFrameServer([(first,), (second,)], connection_interval_seconds=0.1)
    server.start()
    client = TcpPoseStreamClient(
        server.host,
        server.port,
        connect_timeout_seconds=1.0,
        retry_interval_seconds=0.01,
    )

    client.start()
    try:
        assert _next_frame(client, seq=1) == first
        assert _next_frame(client, seq=2) == second
        assert client.error is None
    finally:
        client.close()
        server.close()


def _next_frame(client: TcpPoseStreamClient, *, seq: int) -> PoseFrame:
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if client.error is not None:
            raise AssertionError(f"stream client failed: {client.error}") from client.error
        frame = client.latest()
        if frame is not None and frame.seq == seq:
            return frame
        time.sleep(0.01)
    raise AssertionError(f"timed out waiting for frame {seq}")


def _unused_localhost_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1", 0))
        address = probe.getsockname()
        if not isinstance(address, tuple) or len(address) < 2:
            raise AssertionError(f"unexpected probe address: {address!r}")
        return int(address[1])
    finally:
        probe.close()


def _empty_payload() -> PosePayload:
    return PosePayload(
        global_orient=[0.0, 0.0, 0.0],
        body_pose=[[0.0, 0.0, 0.0] for _ in range(21)],
        left_hand_pose=[[0.0, 0.0, 0.0] for _ in range(15)],
        right_hand_pose=[[0.0, 0.0, 0.0] for _ in range(15)],
        jaw_pose=[0.0, 0.0, 0.0],
        betas=[0.0 for _ in range(10)],
        expression=[0.0 for _ in range(10)],
        transl=[0.0, 0.0, 0.0],
    )


class _FrameServer:
    def __init__(
        self,
        frames: Iterable[PoseFrame],
        *,
        frame_interval_seconds: float = 0.0,
    ) -> None:
        self._frames = tuple(frames)
        self._frame_interval_seconds = frame_interval_seconds
        self._address: tuple[str, int] | None = None
        self._done = Event()
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(1)
        self._thread = Thread(target=self._run, daemon=True)

    @property
    def host(self) -> str:
        if self._address is None:
            raise AssertionError("server has not started")
        return self._address[0]

    @property
    def port(self) -> int:
        if self._address is None:
            raise AssertionError("server has not started")
        return self._address[1]

    def start(self) -> None:
        address = self._server.getsockname()
        if not isinstance(address, tuple) or len(address) < 2:
            raise AssertionError(f"unexpected server address: {address!r}")
        self._address = (str(address[0]), int(address[1]))
        self._thread.start()

    def wait_done(self) -> None:
        if not self._done.wait(timeout=2):
            raise AssertionError("server did not send frames")

    def close(self) -> None:
        self._server.close()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        with self._server:
            connection, _address = self._server.accept()
            with connection, connection.makefile("wb") as writer:
                for index, frame in enumerate(self._frames):
                    if index > 0 and self._frame_interval_seconds > 0:
                        time.sleep(self._frame_interval_seconds)
                    writer.write(encode_pose_frame(frame).encode("utf-8") + b"\n")
                    writer.flush()
        self._done.set()


class _ReconnectFrameServer:
    def __init__(
        self,
        connection_frames: Iterable[Iterable[PoseFrame]],
        *,
        connection_interval_seconds: float = 0.0,
    ) -> None:
        self._connection_frames = tuple(tuple(frames) for frames in connection_frames)
        self._connection_interval_seconds = connection_interval_seconds
        self._address: tuple[str, int] | None = None
        self._done = Event()
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(len(self._connection_frames))
        self._thread = Thread(target=self._run, daemon=True)

    @property
    def host(self) -> str:
        if self._address is None:
            raise AssertionError("server has not started")
        return self._address[0]

    @property
    def port(self) -> int:
        if self._address is None:
            raise AssertionError("server has not started")
        return self._address[1]

    def start(self) -> None:
        address = self._server.getsockname()
        if not isinstance(address, tuple) or len(address) < 2:
            raise AssertionError(f"unexpected server address: {address!r}")
        self._address = (str(address[0]), int(address[1]))
        self._thread.start()

    def close(self) -> None:
        self._server.close()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        with self._server:
            for index, frames in enumerate(self._connection_frames):
                if index > 0 and self._connection_interval_seconds > 0:
                    time.sleep(self._connection_interval_seconds)
                connection, _address = self._server.accept()
                with connection, connection.makefile("wb") as writer:
                    for frame in frames:
                        writer.write(encode_pose_frame(frame).encode("utf-8") + b"\n")
                        writer.flush()
        self._done.set()
