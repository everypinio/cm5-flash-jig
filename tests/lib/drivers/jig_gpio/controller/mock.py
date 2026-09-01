from typing import Any

from ..constants import JIG_GPIO_CONFIG
from ..interfaces import JigGPIOControllerInterface


class MockJigGPIOController(JigGPIOControllerInterface):
    """Mock implementation of JigGPIOControllerInterface for testing without hardware."""

    def __init__(self, gpio: Any) -> None:
        self._states = {pin.name: bool(pin.initial) for pin in JIG_GPIO_CONFIG}
        self._states["DUT_PRESENT"] = False
        self._states["INA_ALERT"] = True

    def is_dut_present(self) -> bool:
        return True

    def set_boot_mode(self, active: bool) -> None:
        self._states["nRPI_BOOT"] = not active

    def is_boot_mode_active(self) -> bool:
        return not self._states["nRPI_BOOT"]

    def is_led_active(self, led_name: str) -> bool:
        return True

    def get_all_states(self) -> dict[str, bool]:
        return dict(self._states)

    def read_pin(self, pin: int) -> bool:
        for config in JIG_GPIO_CONFIG:
            if config.pin == pin:
                return self._states[config.name]
        raise KeyError(f"Unknown JIG GPIO pin: {pin}")

    def set_dut_power_enabled(self, enabled: bool) -> None:
        self._states["OUT_EN"] = enabled

    def is_dut_power_enabled(self) -> bool:
        return self._states["OUT_EN"]

    def is_dut_power_fault_active(self) -> bool:
        return not self._states["INA_ALERT"]
