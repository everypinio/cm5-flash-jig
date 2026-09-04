from __future__ import annotations

import os
import time
from pathlib import Path

import hardpy
import pytest

from tests.env import settings
from tests.lib.drivers.display.dfr0997_operator_panel import DFR0997OperatorPanel
from tests.lib.drivers.jig_gpio import JigGPIOController
from tests.lib.drivers.jig_gpio.constants import DUT_PRESENT, LED_NACT
from tests.lib.hardpy_helpers.cm5_hardpy_dut_info import set_dut_metadata_from_boot_info
from tests.lib.hardpy_helpers.messages import (
    fail_with_operator_message,
    set_message,
)
from tests.lib.hardpy_helpers.reports import set_measurement, set_numeric_measurement
from tests.lib.hardpy_helpers.utils import _hardpy_enabled
from tests.lib.utils.bootlog import (
    open_uart,
    read_uart_boot_log,
    write_boot_log,
)
from tests.lib.utils.cm5_boot_info import (
    DUT_INFO_FIELDS,
    infer_cm5_part_number,
    parse_boot_info,
)
from tests.lib.utils.dut_presence import wait_for_dut_present

pytestmark = [
    pytest.mark.module_name("3. CM5 - Boot Verification"),
    pytest.mark.critical,
    pytest.mark.hold_power_for_module,
]

def _set_boot_log_artifact(
    request: pytest.FixtureRequest,
    *,
    log_text: str,
    log_path: Path,
    boot_info: dict[str, str],
    variant_info: dict[str, object],
    saw_login: bool,
    fatal_matches: list[str],
    success_phrase: str,
    timeout_s: float,
) -> None:
    if not _hardpy_enabled(request):
        return

    hardpy.set_case_artifact(
        {
            "artifact_type": "dut_boot_log",
            "success_phrase": success_phrase,
            "success_phrase_seen": saw_login,
            "timeout_s": timeout_s,
            "fatal_markers": fatal_matches,
            "dut_info": {
                name: boot_info.get(name, "not found") for name in DUT_INFO_FIELDS
            },
            "cm5_variant": variant_info,
            "log_path": str(log_path),
            "log_text": log_text,
        }
    )


def _set_boot_dut_info(
    request: pytest.FixtureRequest,
    boot_info: dict[str, str],
    variant_info: dict[str, object],
) -> None:
    if not _hardpy_enabled(request):
        return

    set_dut_metadata_from_boot_info(boot_info, variant_info)


def _wait_for_active_low_led(
    controller: JigGPIOController,
    pin: int,
    *,
    timeout_s: float,
    poll_s: float,
    require_transition: bool,
) -> bool:
    first = controller.read_pin(pin)
    last = first
    saw_active = not first
    saw_transition = False
    deadline = time.monotonic() + timeout_s

    while time.monotonic() < deadline:
        state = controller.read_pin(pin)
        saw_active = saw_active or not state
        saw_transition = saw_transition or state != last
        if saw_active and (saw_transition or not require_transition):
            return True
        last = state
        time.sleep(poll_s)

    return saw_active and (saw_transition or not require_transition)


UART_BOOT_LOG_3: str | None = None
SAW_LOGIN: bool = False
FATAL_MATCHES: list[str] = []

@pytest.mark.case_name("3.1. Execute normal boot")
def test_execute_normal_boot(
    request: pytest.FixtureRequest, display_panel: DFR0997OperatorPanel, gpio_controller: JigGPIOController, dut_power
) -> None:
    global UART_BOOT_LOG_3, SAW_LOGIN, FATAL_MATCHES

    set_message(
        request,
        "Power-cycling DUT and capturing boot log",
        "Boot check",
    )

    voltage = settings.DUT_POWER_NOMINAL_V
    current = settings.DUT_POWER_CURRENT_LIMIT_A
    boot_timeout_s = settings.DUT_BOOT_TIMEOUT_S
    uart_device = settings.CM_FLASHER_UART_DEVICE
    uart_baud = settings.CM_FLASHER_UART_BAUD
    success_phrase = settings.DUT_BOOT_SUCCESS_PHRASE

    uart_fd: int | None = None

    try:
        display_panel.terminal_start("Boot check")

        if not settings.CM_FLASHER_ENABLE_POWER_WRITE:
            fail_with_operator_message(
                request,
                "Set CM_FLASHER_ENABLE_POWER_WRITE=1 to allow this test to power-cycle DUT",
                "Boot check",
            )

        dut_power.disable()
        set_measurement(request, "DUT power before boot check", "OFF")
        display_panel.terminal_log("DUT power OFF")

        uart_fd = open_uart(uart_device, uart_baud)
        set_measurement(request, "DUT UART device", str(uart_device))
        set_numeric_measurement(request, "DUT UART baud", float(uart_baud), "baud")
        display_panel.terminal_log("UART log capture")

        assert wait_for_dut_present(request, display_panel, gpio_controller), (
            f"DUT_PRESENT on GPIO{DUT_PRESENT} stayed HIGH after waiting for "
            f"{settings.CM_FLASHER_DUT_PRESENT_TIMEOUT_S} s"
        )

        gpio_controller.set_boot_mode(False)
        set_measurement(request, "nRPI_BOOT", "HIGH")
        display_panel.terminal_log("nRPI_BOOT HIGH")

        dut_power.prepare(voltage_v=voltage, current_limit_a=current)
        dut_power.enable()
        display_panel.terminal_log("DUT power ON")

        assert uart_fd is not None
        UART_BOOT_LOG_3, SAW_LOGIN, FATAL_MATCHES = read_uart_boot_log(
            uart_fd,
            timeout_s=boot_timeout_s,
            success_phrase=success_phrase,
            display=display_panel,
            request=request,
        )

        display_panel.terminal_log("Boot sequence captured")
    except Exception as exc:
        set_message(request, f"Boot execution failed: {exc}", "Boot check")
        raise
    finally:
        if uart_fd is not None and uart_fd != -1:
            os.close(uart_fd)


@pytest.mark.case_name("3.2. Measure post-boot power")
def test_measure_post_boot_power(
    request: pytest.FixtureRequest, display_panel: DFR0997OperatorPanel, dut_power
) -> None:
    set_message(
        request,
        "Measuring voltage and current after boot",
        "Boot check",
    )

    settle_s = settings.DUT_BOOT_POWER_SETTLE_S

    try:
        time.sleep(settle_s)
        measured_voltage = dut_power.read_voltage()
        measured_current = dut_power.read_current()
        set_numeric_measurement(
            request, "Boot check voltage", measured_voltage, "V"
        )
        set_numeric_measurement(
            request, "Boot check current", measured_current, "A"
        )
        display_panel.terminal_log(f"Post-boot: {measured_voltage:.2f} V / {measured_current:.2f} A")
    except Exception as exc:
        set_message(request, f"Post-boot power measurement failed: {exc}", "Boot check")
        raise


@pytest.mark.case_name("3.3. Verify LED activity")
def test_verify_led_activity(
    request: pytest.FixtureRequest, display_panel: DFR0997OperatorPanel, gpio_controller: JigGPIOController
) -> None:
    set_message(
        request,
        "Verifying DUT LED activity",
        "Boot check",
    )

    activity_timeout_s = settings.DUT_BOOT_ACTIVITY_TIMEOUT_S
    activity_poll_s = settings.DUT_BOOT_ACTIVITY_POLL_S
    require_pwr_led = settings.DUT_BOOT_REQUIRE_LED_NPWR
    require_act_led = settings.DUT_BOOT_REQUIRE_LED_NACT
    require_act_transition = settings.DUT_BOOT_REQUIRE_LED_NACT_TRANSITION

    try:
        if require_pwr_led:
            pwr_active = gpio_controller.is_led_active("LED_nPWR")
            set_measurement(
                request, "LED_nPWR active", "yes" if pwr_active else "no"
            )
            if not pwr_active:
                fail_with_operator_message(
                    request,
                    "LED_nPWR did not show active-low DUT power",
                    "Boot check",
                )

        if require_act_led:
            activity_seen = _wait_for_active_low_led(
                gpio_controller,
                LED_NACT,
                timeout_s=activity_timeout_s,
                poll_s=activity_poll_s,
                require_transition=require_act_transition,
            )
            set_measurement(
                request, "LED_nACT activity", "yes" if activity_seen else "no"
            )
            if not activity_seen:
                fail_with_operator_message(
                    request,
                    "LED_nACT did not show boot/storage activity",
                    "Boot check",
                )

        display_panel.terminal_log("LED activity verified")
    except Exception as exc:
        set_message(request, f"LED activity check failed: {exc}", "Boot check")
        raise


@pytest.mark.case_name("3.4. Analyze boot logs")
def test_analyze_boot_log(
    request: pytest.FixtureRequest, display_panel: DFR0997OperatorPanel
) -> None:
    set_message(
        request,
        "Analyzing boot log and extracting metadata",
        "Boot check",
    )

    if UART_BOOT_LOG_3 is None:
        pytest.skip("No UART boot log available to analyze.")

    boot_timeout_s = settings.DUT_BOOT_TIMEOUT_S
    success_phrase = settings.DUT_BOOT_SUCCESS_PHRASE

    try:
        log_path = write_boot_log(UART_BOOT_LOG_3)
        boot_info = parse_boot_info(UART_BOOT_LOG_3)
        variant_info = infer_cm5_part_number(UART_BOOT_LOG_3)
        _set_boot_dut_info(request, boot_info, variant_info)
        _set_boot_log_artifact(
            request,
            log_text=UART_BOOT_LOG_3,
            log_path=log_path,
            boot_info=boot_info,
            variant_info=variant_info,
            saw_login=SAW_LOGIN,
            fatal_matches=FATAL_MATCHES,
            success_phrase=success_phrase,
            timeout_s=boot_timeout_s,
        )

        set_measurement(request, "DUT boot log path", str(log_path))
        set_measurement(request, "DUT boot log artifact", "stored")
        set_numeric_measurement(
            request, "DUT boot log bytes", float(len(UART_BOOT_LOG_3.encode("utf-8"))), "B"
        )
        for name in DUT_INFO_FIELDS:
            set_measurement(
                request, f"DUT {name}", boot_info.get(name, "not found")
            )
        for name, value in variant_info.items():
            set_measurement(request, f"DUT CM5 {name}", str(value))

        if FATAL_MATCHES:
            set_measurement(
                request, "DUT boot fatal markers", ", ".join(FATAL_MATCHES)
            )

        if not SAW_LOGIN:
            details = ""
            if FATAL_MATCHES:
                details = " Fatal marker(s): " + ", ".join(FATAL_MATCHES)
            fail_with_operator_message(
                request,
                f"DUT did not reach {success_phrase!r} within {boot_timeout_s:.1f} s.{details}",
                "Boot check",
            )

        set_measurement(request, "DUT boot success phrase", success_phrase)
        set_measurement(request, "boot check", "passed")
        display_panel.terminal_log("Boot check passed")
    except Exception as exc:
        set_message(request, f"Boot log analysis failed: {exc}", "Boot check")
        raise
