import pytest
from corridorrig_contracts import SerialDecodeError, parse_serial_line


def test_parses_eight_channels() -> None:
    line = "0.00,12.34,-360.50,7200.00,0.01,-0.01,180.00,359.99"
    assert parse_serial_line(line) == [0.0, 12.34, -360.5, 7200.0, 0.01, -0.01, 180.0, 359.99]


def test_tolerates_crlf_and_whitespace() -> None:
    assert parse_serial_line("1,2,3,4,5,6,7,8\r\n") == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]


def test_rejects_wrong_channel_count() -> None:
    with pytest.raises(SerialDecodeError, match="expected 8"):
        parse_serial_line("1,2,3")


def test_rejects_non_numeric_value() -> None:
    with pytest.raises(SerialDecodeError, match="non-numeric"):
        parse_serial_line("1,2,3,4,five,6,7,8")


def test_rejects_startup_banner_noise() -> None:
    with pytest.raises(SerialDecodeError):
        parse_serial_line("CH5: 123.4 degrees")
