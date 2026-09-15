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
from tests.lib.utils.dut_presence import wait_for_dut_not_present

pytestmark = [
    pytest.mark.module_name("2. Hardware Validations"),
    pytest.mark.critical,
]

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


@pytest.mark.case_name("2.2. DUT power subsystem self-test")
def test_dut_power_self_test(
    request: pytest.FixtureRequest,
    display_panel: DFR0997OperatorPanel,
    gpio_controller: JigGPIOController,
    dut_power,
) -> None:
    set_message(request, "Checking DUT power subsystem", "DUT power self-test")

    voltage = settings.DUT_POWER_NOMINAL_V
    current_limit = settings.DUT_POWER_CURRENT_LIMIT_A
    min_voltage = settings.DUT_POWER_MIN_V
    max_voltage = settings.DUT_POWER_MAX_V
    off_max_voltage = settings.DUT_POWER_OFF_MAX_V
    idle_current_max = settings.DUT_POWER_IDLE_CURRENT_MAX_A

    set_measurement(request, "DUT power backend", dut_power.backend_name)
    set_numeric_measurement(request, "DUT power nominal voltage", voltage, "V")
    set_numeric_measurement(request, "DUT current limit", current_limit, "A")

    try:
        display_panel.terminal_start("DUT power self-test")
        display_panel.terminal_log("Checking DUT_PRESENT")
        assert wait_for_dut_not_present(request, display_panel, gpio_controller), (
            f"DUT_PRESENT on GPIO{DUT_PRESENT} stayed LOW after waiting for "
            f"{settings.CM_FLASHER_DUT_PRESENT_TIMEOUT_S} s"
        )
        set_measurement(request, "DUT_PRESENT before power test", "HIGH")
        display_panel.terminal_log("DUT_PRESENT HIGH")

        identity = dut_power.identity()
        set_measurement(request, "DUT power identity", identity)
        assert identity, "DUT power identity response is empty"
        display_panel.terminal_log(identity)

        if not settings.CM_FLASHER_ENABLE_POWER_WRITE:
            fail_with_operator_message(
                request,
                "Set CM_FLASHER_ENABLE_POWER_WRITE=1 to allow this test to toggle DUT power",
            )

        dut_power.disable()
        time.sleep(settings.DUT_POWER_SETTLE_S)
        off_voltage = dut_power.read_voltage()
        set_numeric_measurement(request, "DUT voltage while disabled", off_voltage, "V")
        if off_voltage > off_max_voltage:
            fail_with_operator_message(
                request,
                f"DUT voltage is {off_voltage:.3f} V while disabled; "
                f"expected no more than {off_max_voltage:.3f} V",
                "DUT power self-test",
            )

        dut_power.prepare(voltage_v=voltage, current_limit_a=current_limit)
        if dut_power.has_fault():
            fail_with_operator_message(
                request,
                f"DUT power fault before enable: {dut_power.diagnostics()}",
                "DUT power self-test",
            )

        set_message(
            request,
            f"DUT power ON: {voltage:.3f} V, limit {current_limit:.3f} A",
            "DUT power self-test",
        )
        dut_power.enable()
        display_panel.terminal_log("DUT power ON")
        time.sleep(settings.DUT_POWER_SETTLE_S)
        measured_voltage = dut_power.read_voltage()
        measured_current = dut_power.read_current()
        set_numeric_measurement(request, "DUT power measured voltage", measured_voltage, "V")
        set_numeric_measurement(request, "DUT power measured current", measured_current, "A")

        for name, value in dut_power.diagnostics().items():
            set_measurement(request, f"DUT power {name}", str(value))

        assert min_voltage <= measured_voltage <= max_voltage, (
            f"DUT power measured voltage {measured_voltage:.3f} V is outside "
            f"{min_voltage:.3f}..{max_voltage:.3f} V"
        )
        if dut_power.backend_name == "onboard_ina229":
            assert abs(measured_current) <= idle_current_max, (
                f"INA229 measured {measured_current:.3f} A with DUT removed; "
                f"expected no more than {idle_current_max:.3f} A"
            )
        assert not dut_power.has_fault(), (
            f"DUT power fault after enable: {dut_power.diagnostics()}"
        )
        display_panel.terminal_log(f"Measured {measured_voltage:.3f} V")
    except Exception as exc:
        set_message(request, f"DUT power check failed: {exc}", "DUT power self-test")
        raise
    finally:
        dut_power.disable()
