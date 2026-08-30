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
)
from tests.lib.hardpy_helpers.reports import set_measurement, set_numeric_measurement
from tests.lib.utils.dut_presence import wait_for_dut_present

POWER_LINE_SPECS = (
    ("DUT_5V", 5.0, "ADC_5V_CHANNEL", "ADC_5V_SCALE", "ADC_5V_MIN", "ADC_5V_MAX"),
    ("CM5_3V3", 3.3, "ADC_3V3_CHANNEL", "ADC_3V3_SCALE", "ADC_3V3_MIN", "ADC_3V3_MAX"),
    ("CM5_1V8", 1.8, "ADC_1V8_CHANNEL", "ADC_1V8_SCALE", "ADC_1V8_MIN", "ADC_1V8_MAX"),
)

pytestmark = [
    pytest.mark.module_name("1. Hardware Validations"),
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

@pytest.mark.case_name("1.1. Verify DUT installation")
def test_verify_dut_installation(
    request: pytest.FixtureRequest, display_panel: DFR0997OperatorPanel, gpio_controller: JigGPIOController, power_block
) -> None:
    channel = settings.PWRBLOCK_CHANNEL

    display_panel.terminal_start("Install DUT")
    display_panel.terminal_log("Switching PowerBlock off")
    try:
        power_block.set_supply(channel, "OFF")
    except Exception as exc:
        fail_with_operator_message(
            request,
            f"Could not switch PowerBlock output OFF before DUT install: {exc}",
            "Install DUT",
        )
    else:
        set_measurement(request, "PowerBlock output before DUT install", "OFF")
        display_panel.terminal_log("PowerBlock output OFF")

    assert gpio_controller.is_dut_present(), (
        f"DUT_PRESENT on GPIO{DUT_PRESENT} is HIGH although the controller "
        "started the test after lid closure"
    )
    set_measurement(request, "DUT_PRESENT before test", "LOW")
    display_panel.terminal_log("DUT_PRESENT LOW")

@pytest.mark.case_name("1.2. Measure DUT power rails")
def test_measure_dut_power_rails(
    request: pytest.FixtureRequest, display_panel: DFR0997OperatorPanel, gpio_controller: JigGPIOController, power_block, adc_reader
) -> None:
    set_message(
        request,
        "Powering DUT and measuring rails",
        "Power lines",
    )

    resource_name = settings.PWRBLOCK_RESOURCE
    channel = settings.PWRBLOCK_CHANNEL
    voltage = settings.PWRBLOCK_TEST_VOLTAGE or settings.PWRBLOCK_DUT_VOLTAGE
    current = settings.PWRBLOCK_TEST_CURRENT or settings.PWRBLOCK_DUT_CURRENT
    min_input_voltage = settings.PWRBLOCK_DUT_MIN_VOLTAGE
    max_input_voltage = settings.PWRBLOCK_DUT_MAX_VOLTAGE
    settle_s = settings.DUT_POWER_SETTLE_S

    use_adc_stub = settings.MOCK_ADC

    try:
        display_panel.terminal_start("Power lines")
        display_panel.terminal_log("Checking DUT presence")
        assert wait_for_dut_present(request, display_panel, gpio_controller), (
            f"DUT_PRESENT on GPIO{DUT_PRESENT} stayed HIGH after waiting for "
            f"{settings.CM_FLASHER_DUT_PRESENT_TIMEOUT_S} s"
        )

        if not getattr(settings, settings.PWRBLOCK_ENABLE_ENV):
            fail_with_operator_message(
                request,
                f"Set {settings.PWRBLOCK_ENABLE_ENV}=1 to allow this test to power DUT",
                "Power lines",
            )

        display_panel.terminal_log("Powering DUT")

        power_block.set_supply(channel, "OFF")
        power_block.set_voltage(channel, voltage)
        power_block.set_current(channel, current)
        display_panel.terminal_log(f"Set {voltage:.2f} V / {current:.2f} A")
        set_voltage = power_block.get_voltage_setpoint(channel)
        set_numeric_measurement(
            request, "DUT power voltage setpoint", set_voltage, "V"
        )
        if not min_input_voltage <= set_voltage <= max_input_voltage:
            fail_with_operator_message(
                request,
                f"PowerBlock voltage setpoint is {set_voltage:.3f} V, expected "
                f"{min_input_voltage:.3f}..{max_input_voltage:.3f} V. Output was not enabled.",
                "Power lines",
            )

        power_block.set_supply(channel, "ON")
        display_panel.terminal_log("PowerBlock output ON")
        time.sleep(settle_s)
        measured_input = power_block.get_voltage(channel)
        measured_current = power_block.get_current(channel)
        set_numeric_measurement(
            request, "PowerBlock DUT voltage", measured_input, "V"
        )
        set_numeric_measurement(
            request, "PowerBlock DUT current", measured_current, "A"
        )
        if not min_input_voltage <= measured_input <= max_input_voltage:
            fail_with_operator_message(
                request,
                f"PowerBlock measured voltage {measured_input:.3f} V is outside "
                f"{min_input_voltage:.3f}..{max_input_voltage:.3f} V",
                "Power lines",
            )

        if use_adc_stub:
            set_measurement(request, "ADC measurement mode", "stub")
            display_panel.terminal_log("ADC mode: stub")
        else:
            set_measurement(request, "ADC measurement mode", settings.ADC_MODEL)
            display_panel.terminal_log(f"ADC mode: {settings.ADC_MODEL}")

        default_channels = {"DUT_5V": 2, "CM5_3V3": 0, "CM5_1V8": 1}
        failed_rails: list[str] = []
        for (
            name,
            nominal,
            channel_env,
            scale_env,
            min_env,
            max_env,
        ) in POWER_LINE_SPECS:
            if name == "DUT_5V" and not settings.ADC_5V_ENABLED:
                set_measurement(request, f"{name} ADC channel", "disabled")
                display_panel.terminal_log(f"{name}: ADC measurement disabled")
                continue
            adc_channel = getattr(settings, channel_env) or default_channels[name]
            scale = getattr(settings, scale_env) or 1.0
            low_limit = getattr(settings, min_env) or nominal * 0.95
            high_limit = getattr(settings, max_env) or nominal * 1.05
            if use_adc_stub:
                measured = nominal
            else:
                measured = adc_reader.read_voltage(adc_channel, scale=scale)
            set_measurement(request, f"{name} ADC channel", str(adc_channel))
            set_numeric_measurement(request, f"{name} voltage", measured, "V")
            display_panel.terminal_log(f"{name}: {measured:.3f} V")
            if not low_limit <= measured <= high_limit:
                failed_rails.append(
                    f"{name}={measured:.3f} V, expected {low_limit:.3f}..{high_limit:.3f} V"
                )

        if failed_rails:
            fail_with_operator_message(
                request,
                "Voltage out of range: " + "; ".join(failed_rails),
                "Power lines",
            )

        display_panel.terminal_log("Rails in range")
    except Exception as exc:
        set_message(request, f"Power-line check failed: {exc}", "Power lines")
        raise

