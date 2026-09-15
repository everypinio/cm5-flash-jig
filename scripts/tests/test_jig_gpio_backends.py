from __future__ import annotations

import pytest

from tests.lib.drivers.jig_gpio.backends.gpiozero import GpiozeroBackend


class FakeInputDevice:
    calls: list[tuple[int, bool | None, bool | None]] = []

    def __init__(
        self,
        pin: int,
        *,
        pull_up: bool | None,
        active_state: bool | None = None,
    ) -> None:
        self.calls.append((pin, pull_up, active_state))


@pytest.mark.parametrize(
    ("pull", "expected"),
    (("up", True), ("down", False), (None, None)),
)
def test_gpiozero_backend_preserves_pull_mode(
    pull: str | None, expected: bool | None
) -> None:
    backend = GpiozeroBackend.__new__(GpiozeroBackend)
    backend._digital_input_device = FakeInputDevice
    backend._devices = {}
    FakeInputDevice.calls.clear()

    backend.setup_input(21, pull=pull)

    expected_active_state = True if pull is None else None
    assert FakeInputDevice.calls == [(21, expected, expected_active_state)]


def test_gpiozero_backend_rejects_unknown_pull_mode() -> None:
    backend = GpiozeroBackend.__new__(GpiozeroBackend)
    backend._digital_input_device = FakeInputDevice
    backend._devices = {}

    with pytest.raises(ValueError, match="Unsupported GPIO pull mode"):
        backend.setup_input(21, pull="sideways")
