import numpy as np
from posecap_engine.preview import PreviewWindow


class _FakeCv2:
    COLOR_RGB2BGR = 4

    def __init__(self) -> None:
        self.shown: list[str] = []
        self.waited = 0
        self.destroyed: list[str] = []

    def cvtColor(self, image, code):  # noqa: N802 - mirrors cv2 name
        return ("bgr", code)

    def imshow(self, title: str, _image) -> None:
        self.shown.append(title)

    def waitKey(self, _ms: int) -> int:  # noqa: N802 - mirrors cv2 name
        self.waited += 1
        return -1

    def destroyWindow(self, title: str) -> None:  # noqa: N802 - mirrors cv2 name
        self.destroyed.append(title)


def _frame() -> np.ndarray:
    return np.zeros((4, 4, 3), dtype=np.uint8)


def test_offer_shows_each_frame_and_pumps_the_event_loop() -> None:
    cv2 = _FakeCv2()
    window = PreviewWindow(cv2, title="src")

    window.offer(_frame())
    window.offer(_frame())

    assert cv2.shown == ["src", "src"]
    assert cv2.waited >= 2


def test_close_destroys_the_window_once_opened() -> None:
    cv2 = _FakeCv2()
    window = PreviewWindow(cv2, title="src")

    window.offer(_frame())
    window.close()

    assert cv2.destroyed == ["src"]


def test_close_is_a_noop_when_never_shown() -> None:
    cv2 = _FakeCv2()
    window = PreviewWindow(cv2, title="src")

    window.close()

    assert cv2.destroyed == []
