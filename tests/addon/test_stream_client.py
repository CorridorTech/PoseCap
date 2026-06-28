import socket
import time
from collections.abc import Iterable
from threading import Event, Thread

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
        time.sleep(0.05)

        latest = client.latest()
        assert latest == second
        assert client.latest() is None
    finally:
        client.close()
        server.close()


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
    def __init__(self, frames: Iterable[PoseFrame]) -> None:
        self._frames = tuple(frames)
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
                for frame in self._frames:
                    writer.write(encode_pose_frame(frame).encode("utf-8") + b"\n")
                writer.flush()
        self._done.set()
