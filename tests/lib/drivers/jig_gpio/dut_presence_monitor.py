from __future__ import annotations

from typing import Self

from .backends.exceptions import GPIOBackendUnavailable
from .backends.pinctrl import PinctrlBackend
from .backends.raspi_gpio import RaspiGpioBackend
from .constants import DUT_PRESENT
from .interfaces import GPIOBackend


def _make_read_only_backend() -> GPIOBackend:
    errors: list[str] = []
    for name, backend_type in (
        ("pinctrl", PinctrlBackend),
        ("raspi-gpio", RaspiGpioBackend),
    ):
        try:
            backend = backend_type()
            backend.setup_input(DUT_PRESENT, pull="up")
            return backend
        except Exception as exc:
            errors.append(f"{name}: {exc}")

    raise GPIOBackendUnavailable(
        "No read-only GPIO backend is available (" + "; ".join(errors) + ")"
    )


class DutPresenceMonitor:
    """Read DUT_PRESENT without claiming the JIG output GPIOs."""

    def __init__(self, backend: GPIOBackend | None = None) -> None:
        self.backend = backend
        self._initialized = False

    def __enter__(self) -> Self:
        self.initialize()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def initialize(self) -> None:
        if self._initialized:
            return
        if self.backend is None:
            self.backend = _make_read_only_backend()
        else:
            self.backend.setup_input(DUT_PRESENT, pull="up")
        self._initialized = True

    def is_dut_present(self) -> bool:
        if not self._initialized:
            raise RuntimeError("DUT presence monitor is not initialized")
        assert self.backend is not None
        return not self.backend.read(DUT_PRESENT)

    def restore_input(self) -> None:
        """Restore the pull-up after pytest releases its GPIO fixture."""
        if not self._initialized or self.backend is None:
            raise RuntimeError("DUT presence monitor is not initialized")
        self.backend.setup_input(DUT_PRESENT, pull="up")

    def close(self) -> None:
        if self.backend is not None:
            self.backend.close()
        self._initialized = False
