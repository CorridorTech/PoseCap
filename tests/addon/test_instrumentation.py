import logging
from logging.handlers import RotatingFileHandler

import pytest
from posecap_addon.instrumentation import ApplyTimeInstrumentation, configure_addon_logging


def test_apply_time_instrumentation_logs_info_only_on_interval() -> None:
    logger = _FakeLogger()
    clock = _ManualClock([0.0, 0.5, 0.9, 1.0])
    instrumentation = ApplyTimeInstrumentation(
        logger=logger,
        clock=clock,
        interval_seconds=1.0,
    )

    instrumentation.record(0.010)
    instrumentation.record(0.020)

    assert logger.infos == []

    instrumentation.record(0.030)

    message, args = logger.infos[0]
    assert message == "pose_apply_time frames=%d avg_ms=%.3f max_ms=%.3f"
    assert args[0] == 3
    assert args[1] == pytest.approx(20.0)
    assert args[2] == pytest.approx(30.0)


def test_configure_addon_logging_installs_bounded_rotating_file_handler(tmp_path) -> None:
    logger = logging.getLogger(f"posecap-test-{tmp_path.name}")
    logger.handlers.clear()
    log_path = tmp_path / "posecap-addon.log"

    configured = configure_addon_logging(
        log_path,
        logger=logger,
        max_bytes=1234,
        backup_count=2,
    )
    configure_addon_logging(
        log_path,
        logger=logger,
        max_bytes=1234,
        backup_count=2,
    )
    configured.info("hello")

    handlers = [
        handler for handler in configured.handlers if isinstance(handler, RotatingFileHandler)
    ]
    assert len(handlers) == 1
    assert handlers[0].maxBytes == 1234
    assert handlers[0].backupCount == 2
    assert log_path.exists()


class _FakeLogger:
    def __init__(self) -> None:
        self.infos: list[tuple[str, tuple[object, ...]]] = []

    def info(self, message: str, *args: object) -> None:
        self.infos.append((message, args))


class _ManualClock:
    def __init__(self, values: list[float]) -> None:
        self._values = values

    def __call__(self) -> float:
        if not self._values:
            raise AssertionError("clock exhausted")
        return self._values.pop(0)
