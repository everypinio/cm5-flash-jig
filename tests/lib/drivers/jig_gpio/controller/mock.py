from typing import Any

from ..constants import JIG_GPIO_CONFIG
from ..interfaces import JigGPIOControllerInterface


class MockJigGPIOController(JigGPIOControllerInterface):
    """Mock implementation of JigGPIOControllerInterface for testing without hardware."""

    def __init__(self, gpio: Any) -> None:
        pass

    def is_dut_present(self) -> bool:
        return True

    def set_boot_mode(self, active: bool) -> None:
        pass

    def is_boot_mode_active(self) -> bool:
        return True

    def is_led_active(self, led_name: str) -> bool:
        return True

    def get_all_states(self) -> dict[str, bool]:
        return {pin.name: True for pin in JIG_GPIO_CONFIG}

    def read_pin(self, pin: int) -> bool:
        return False  # Mock as active low for LEDs
