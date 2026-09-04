import errno
from unittest.mock import Mock

import pytest

from tests.lib.drivers.display import dfr0997_display as display_module


def _display_with_bus(bus: Mock) -> display_module.DFR0997I2CDisplay:
    display = display_module.DFR0997I2CDisplay.__new__(
        display_module.DFR0997I2CDisplay
    )
    display.address = 0x2C
    display.chunk_delay_s = 0
    display.bus = bus
    return display


@pytest.mark.parametrize(
    "error_code",
    [errno.EIO, getattr(errno, "EREMOTEIO", 121)],
)
def test_send_retries_transient_i2c_errors(
    monkeypatch: pytest.MonkeyPatch,
    error_code: int,
) -> None:
    bus = Mock()
    bus.i2c_rdwr.side_effect = [
        OSError(error_code, "temporary I2C error"),
        None,
    ]
    display = _display_with_bus(bus)
    monkeypatch.setattr(display_module.time, "sleep", lambda _seconds: None)

    display.send([0x55, 0xAA])

    assert bus.i2c_rdwr.call_count == 2


def test_send_raises_non_retryable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus = Mock()
    bus.i2c_rdwr.side_effect = OSError(errno.EINVAL, "invalid request")
    display = _display_with_bus(bus)
    monkeypatch.setattr(display_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(OSError, match="invalid request"):
        display.send([0x55, 0xAA])

    assert bus.i2c_rdwr.call_count == 1


def test_send_raises_after_retry_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error_code = getattr(errno, "EREMOTEIO", 121)
    bus = Mock()
    bus.i2c_rdwr.side_effect = OSError(error_code, "display unavailable")
