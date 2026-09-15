from __future__ import annotations

from .interfaces import DutPowerCapabilities, DutPowerControllerInterface
from .onboard import OnboardIna229DutPower
from .pwrblock import PwrBlockDutPower


def make_dut_power(gpio_controller):
    # Keep package imports lightweight; runtime settings are loaded only when
    # the fixture actually constructs a hardware controller.
    from .factory import make_dut_power as make_from_settings

    return make_from_settings(gpio_controller)


__all__ = [
    "DutPowerCapabilities",
    "DutPowerControllerInterface",
    "OnboardIna229DutPower",
    "PwrBlockDutPower",
    "make_dut_power",
]
