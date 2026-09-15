from abc import ABC, abstractmethod
from typing import Protocol


class GPIOBackend(Protocol):
    name: str

    def setup_input(self, pin: int, *, pull: str | None) -> None: ...

    def setup_output(self, pin: int, *, initial: bool) -> None: ...

    def read(self, pin: int) -> bool: ...

    def write(self, pin: int, value: bool) -> None: ...

    def close(self) -> None: ...


class JigGPIOControllerInterface(ABC):
    """High-level interface for JIG GPIO operations."""

    @abstractmethod
    def is_dut_present(self) -> bool:
        """Return True if the DUT is detected in the JIG."""

    @abstractmethod
    def set_boot_mode(self, active: bool) -> None:
        """Enable or disable USB boot mode.
        active=True: USB boot mode active (nRPI_BOOT LOW)
        active=False: USB boot mode inactive (nRPI_BOOT HIGH)
        """

    @abstractmethod
    def is_boot_mode_active(self) -> bool:
        """Return True if USB boot mode is currently active."""

    @abstractmethod
    def is_led_active(self, led_name: str) -> bool:
        """Return True if the specified LED is active.
        LEDs are active LOW.
        """

    @abstractmethod
    def get_all_states(self) -> dict[str, bool]:
        """Return the current state of all JIG GPIO pins."""

    @abstractmethod
    def read_pin(self, pin: int) -> bool:
        """Read the raw state of a GPIO pin."""

    @abstractmethod
    def set_dut_power_enabled(self, enabled: bool) -> None:
        """Drive the active-high OUT_EN signal for the DUT power switch."""

    @abstractmethod
    def is_dut_power_enabled(self) -> bool:
        """Return the commanded OUT_EN state."""

    @abstractmethod
    def is_dut_power_fault_active(self) -> bool:
        """Return True while the active-low INA_ALERT signal is asserted."""
