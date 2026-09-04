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
    request: pytest.FixtureRequest, display_panel: DFR0997OperatorPanel, gpio_controller: JigGPIOController, dut_power
) -> None:
    display_panel.terminal_start("Install DUT")
    display_panel.terminal_log("Switching DUT power off")
    try:
        dut_power.disable()
    except Exception as exc:
        fail_with_operator_message(
            request,
            f"Could not switch DUT power OFF before DUT install: {exc}",
            "Install DUT",
        )
    else:
        set_measurement(request, "DUT power before install", "OFF")
        display_panel.terminal_log("DUT power OFF")

    assert gpio_controller.is_dut_present(), (
        f"DUT_PRESENT on GPIO{DUT_PRESENT} is HIGH although the controller "
        "started the test after lid closure"
    )
    set_measurement(request, "DUT_PRESENT before test", "LOW")
    display_panel.terminal_log("DUT_PRESENT LOW")

@pytest.mark.case_name("1.2. Measure DUT power rails")
def test_measure_dut_power_rails(
    request: pytest.FixtureRequest, display_panel: DFR0997OperatorPanel, gpio_controller: JigGPIOController, dut_power, adc_reader
) -> None:
    set_message(
        request,
        "Powering DUT and measuring rails",
        "Power lines",
    )

    voltage = settings.DUT_POWER_NOMINAL_V
    current = settings.DUT_POWER_CURRENT_LIMIT_A
    min_input_voltage = settings.DUT_POWER_MIN_V
    max_input_voltage = settings.DUT_POWER_MAX_V
    settle_s = settings.DUT_POWER_SETTLE_S

    use_adc_stub = settings.MOCK_ADC

    try:
        display_panel.terminal_start("Power lines")
        display_panel.terminal_log("Checking DUT presence")
        assert wait_for_dut_present(request, display_panel, gpio_controller), (
            f"DUT_PRESENT on GPIO{DUT_PRESENT} stayed HIGH after waiting for "
            f"{settings.CM_FLASHER_DUT_PRESENT_TIMEOUT_S} s"
        )

        if not settings.CM_FLASHER_ENABLE_POWER_WRITE:
            fail_with_operator_message(
                request,
                "Set CM_FLASHER_ENABLE_POWER_WRITE=1 to allow this test to power DUT",
                "Power lines",
            )

        display_panel.terminal_log("Powering DUT")

        dut_power.disable()
        dut_power.prepare(voltage_v=voltage, current_limit_a=current)
        set_measurement(request, "DUT power backend", dut_power.backend_name)
        set_numeric_measurement(request, "DUT power nominal voltage", voltage, "V")
        set_numeric_measurement(request, "DUT current limit", current, "A")
        display_panel.terminal_log(f"Prepared {voltage:.2f} V / {current:.2f} A")

        dut_power.enable()
        display_panel.terminal_log("DUT power ON")
        time.sleep(settle_s)
        measured_input = dut_power.read_voltage()
        measured_current = dut_power.read_current()
        set_numeric_measurement(
            request, "DUT input voltage", measured_input, "V"
        )
        set_numeric_measurement(
            request, "DUT input current", measured_current, "A"
        )
        if not min_input_voltage <= measured_input <= max_input_voltage:
            fail_with_operator_message(
                request,
                f"DUT input voltage {measured_input:.3f} V is outside "
                f"{min_input_voltage:.3f}..{max_input_voltage:.3f} V",
                "Power lines",
            )
        if dut_power.has_fault():
            fail_with_operator_message(
                request,
                f"DUT power subsystem reports a fault: {dut_power.diagnostics()}",
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

