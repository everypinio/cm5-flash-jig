from __future__ import annotations

from typing import Any

from tests.env import settings
from tests.lib.drivers.ina229 import INA229, MockINA229

from .interfaces import DutPowerControllerInterface
from .onboard import OnboardIna229DutPower
from .pwrblock import PwrBlockDutPower


def make_dut_power(gpio_controller: Any) -> DutPowerControllerInterface:
    backend = settings.DUT_POWER_BACKEND.strip().lower().replace("-", "_")
    if backend in {"pwrblock", "power_block"}:
        from tests.lib.drivers.power_block import PowerBlockDriver

        driver = PowerBlockDriver(resource_name=settings.PWRBLOCK_RESOURCE)
        return PwrBlockDutPower(driver, channel=settings.PWRBLOCK_CHANNEL)

    if backend in {"onboard", "onboard_ina229", "gpio_ina229"}:
        if settings.MOCK_INA229:
            monitor = MockINA229(voltage_v=settings.DUT_POWER_NOMINAL_V)
        else:
            monitor = INA229(
                bus=settings.INA229_SPI_BUS,
                device=settings.INA229_SPI_DEVICE,
                max_speed_hz=settings.INA229_SPI_MAX_HZ,
                shunt_ohms=settings.INA229_SHUNT_OHMS,
                max_current_a=settings.DUT_POWER_CURRENT_LIMIT_A,
                adc_range=settings.INA229_ADC_RANGE,
                conversion_time_code=settings.INA229_CONVERSION_TIME_CODE,
            )
        return OnboardIna229DutPower(
            gpio_controller,
            monitor,
            nominal_voltage_v=settings.DUT_POWER_NOMINAL_V,
            maximum_current_a=settings.DUT_POWER_CURRENT_LIMIT_A,
        )

    raise ValueError(
        f"Unsupported DUT_POWER_BACKEND={settings.DUT_POWER_BACKEND!r}; "
        "expected 'onboard_ina229' or 'pwrblock'"
    )
