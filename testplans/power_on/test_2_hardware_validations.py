from __future__ import annotations

import time

import pytest

from tests.env import settings
from tests.lib.drivers.display.dfr0997_operator_panel import DFR0997OperatorPanel
from tests.lib.drivers.jig_gpio import JigGPIOController
from tests.lib.drivers.jig_gpio.constants import DUT_PRESENT
from tests.lib.hardpy_helpers.messages import (
    fail_with_operator_message,
    set_message,
    set_operator_message,
)
from tests.lib.hardpy_helpers.reports import set_measurement, set_numeric_measurement
from tests.lib.utils.dut_presence import wait_for_dut_not_present, wait_for_dut_present

POWER_LINE_SPECS = (
    ("DUT_5V", 5.0, "ADC_5V_CHANNEL", "ADC_5V_SCALE", "ADC_5V_MIN", "ADC_5V_MAX"),
)

pytestmark = [
    pytest.mark.module_name("2. Hardware Validations"),
    pytest.mark.critical,
]

def _record_powerblock_query(
    request: pytest.FixtureRequest,
    driver: object,
    command: str,
) -> str:
    try:
        response = driver.query_raw(command).replace("\x00", "").strip()
    except Exception as exc:
        response = f"<error: {exc}>"

    line = f"{command} => {response}"
    print(line)
    set_measurement(request, f"PowerBlock {command}", response)
    return response

@pytest.mark.case_name("2.1. Verify DUT is removed")
def test_verify_dut_removed(
    request: pytest.FixtureRequest, display_panel: DFR0997OperatorPanel, gpio_controller: JigGPIOController
) -> None:
    set_message(request, "Preparing for work", "Stand readiness")
    display_panel.show_starting()
    display_panel.terminal_log("Preparing for work")
    set_measurement(request, "display_panel", "Preparing for work")

    assert wait_for_dut_not_present(request, display_panel, gpio_controller), (
        f"DUT_PRESENT on GPIO{DUT_PRESENT} stayed LOW after waiting for "
        f"{settings.CM_FLASHER_DUT_PRESENT_TIMEOUT_S} s"
    )

    states = gpio_controller.get_all_states()
    for name, state in states.items():
        set_measurement(request, name, "HIGH" if state else "LOW")
    display_panel.terminal_log("GPIO inputs ready")


@pytest.mark.case_name("2.2. PowerBlock functionality self-test")
def test_powerblock_self_test(
    request: pytest.FixtureRequest, display_panel: DFR0997OperatorPanel, gpio_controller: JigGPIOController, power_block
) -> None:
    set_message(request, "Checking PowerBlock / PowerBlock output", "PowerBlock self-test")

    resource_name = settings.PWRBLOCK_RESOURCE
    channel = settings.PWRBLOCK_CHANNEL
    voltage = settings.PWRBLOCK_TEST_VOLTAGE
    current = settings.PWRBLOCK_TEST_CURRENT
    min_voltage = settings.PWRBLOCK_TEST_MIN_VOLTAGE
    max_voltage = settings.PWRBLOCK_TEST_MAX_VOLTAGE

    set_measurement(request, "PWRBLOCK_RESOURCE", resource_name or "auto")
    set_measurement(request, "PWRBLOCK_CHANNEL", str(channel))
    set_numeric_measurement(request, "PWRBLOCK_TEST_VOLTAGE", voltage, "V")
    set_numeric_measurement(request, "PWRBLOCK_TEST_CURRENT", current, "A")

    try:
        display_panel.terminal_start("PowerBlock self-test")
        display_panel.terminal_log("Checking DUT_PRESENT")
        assert wait_for_dut_not_present(request, display_panel, gpio_controller), (
            f"DUT_PRESENT on GPIO{DUT_PRESENT} stayed LOW after waiting for "
            f"{settings.CM_FLASHER_DUT_PRESENT_TIMEOUT_S} s"
        )
        set_measurement(request, "DUT_PRESENT before PowerBlock", "HIGH")
        display_panel.terminal_log("DUT_PRESENT HIGH")

        identity = power_block.get_uid()
        set_measurement(request, "PowerBlock identity", identity)
        assert identity, "PowerBlock identity response is empty"
        print(f"*IDN? => {identity}")
        display_panel.terminal_log("PowerBlock connected")

        if not getattr(settings, settings.PWRBLOCK_ENABLE_ENV):
            fail_with_operator_message(
                request,
                f"Set {settings.PWRBLOCK_ENABLE_ENV}=1 to allow this test to toggle the PowerBlock output",
            )

        power_block.set_supply(channel, "OFF")
        display_panel.terminal_log("PowerBlock output OFF")
        _record_powerblock_query(request, power_block, "OUTP?")
        power_block.set_voltage(channel, voltage)
        power_block.set_current(channel, current)
        display_panel.terminal_log(f"Set {voltage:.2f} V / {current:.2f} A")
        _record_powerblock_query(request, power_block, "SYST:ERR?")
        _record_powerblock_query(request, power_block, "VOLT?")
        _record_powerblock_query(request, power_block, "CURR?")
        set_voltage = power_block.get_voltage_setpoint(channel)
        set_current = power_block.get_current_setpoint(channel)
        set_numeric_measurement(request, "PowerBlock voltage setpoint", set_voltage, "V")
        set_numeric_measurement(request, "PowerBlock current setpoint", set_current, "A")

        if not min_voltage <= set_voltage <= max_voltage:
            fail_with_operator_message(
                request,
                f"PowerBlock voltage setpoint is {set_voltage:.3f} V, expected "
                f"{min_voltage:.3f}..{max_voltage:.3f} V. Output was not enabled.",
                "PowerBlock self-test",
            )

        set_message(
            request,
            f"PowerBlock output ON: {voltage:.3f} V, limit {current:.3f} A",
            "PowerBlock self-test",
        )
        power_block.set_supply(channel, "ON")
        display_panel.terminal_log("PowerBlock output ON")
        time.sleep(settings.PWRBLOCK_SETTLE_S)
        _record_powerblock_query(request, power_block, "OUTP?")
        _record_powerblock_query(request, power_block, "VOLT?")
        _record_powerblock_query(request, power_block, "MEAS:VOLT?")
        _record_powerblock_query(request, power_block, "CURR?")
        _record_powerblock_query(request, power_block, "MEAS:CURR?")
        _record_powerblock_query(request, power_block, "SYST:ERR?")
        measured_voltage = power_block.get_voltage(channel)
        measured_current = power_block.get_current(channel)
        set_numeric_measurement(request, "PowerBlock measured voltage", measured_voltage, "V")
        set_numeric_measurement(request, "PowerBlock measured current", measured_current, "A")

        assert min_voltage <= measured_voltage <= max_voltage, (
            f"PowerBlock measured voltage {measured_voltage:.3f} V is outside "
            f"{min_voltage:.3f}..{max_voltage:.3f} V"
        )
        display_panel.terminal_log(f"Measured {measured_voltage:.3f} V")
    except Exception as exc:
        set_message(request, f"PowerBlock check failed: {exc}", "PowerBlock self-test")
        raise
