import time

import pytest

from tests.env import settings
from tests.lib.drivers.jig_gpio import JigGPIOController
from tests.lib.hardpy_helpers.messages import (
    clear_operator_message,
    set_message,
    set_operator_message,
)
from tests.utils import (
    set_measurement,
)

DUT_PRESENT_WAIT_MESSAGE = (
    "Remove Compute Module from JIG. Waiting until signal becomes HIGH"
)


DUT_WAIT_HEARTBEAT_S = 1.0
DUT_WAIT_LOG_INTERVAL_S = 30.0


def wait_for_dut_present(
    request: pytest.FixtureRequest,
    display: object,
    controller: JigGPIOController,
) -> bool:
    return _wait_for_dut_present(
        request,
        display,
        controller,
        timeout_s=settings.CM_FLASHER_DUT_PRESENT_TIMEOUT_S,
    )


def _wait_for_dut_present(
    request: pytest.FixtureRequest,
    display: object,
    controller: JigGPIOController,
    *,
    timeout_s: float,
) -> bool:
    if settings.MOCK_GPIO:
        return True
    if controller.is_dut_present():
        return True

    message = "Install Compute Module in JIG. Close the JIG lid."
    set_operator_message(request, message, "Install DUT")
    display.show_waiting_for_dut(0)
    set_measurement(request, "DUT_PRESENT initial", "HIGH")

    poll_s = settings.CM_FLASHER_DUT_PRESENT_POLL_S
    started_at = time.monotonic()
    deadline = started_at + timeout_s
    last_heartbeat_s = 0
    next_log_at_s = DUT_WAIT_LOG_INTERVAL_S

    while time.monotonic() < deadline:
        if controller.is_dut_present():
            elapsed_s = time.monotonic() - started_at
            set_measurement(request, "DUT_PRESENT final", "LOW")
            set_measurement(request, "DUT installation wait", f"{elapsed_s:.1f} s")
            clear_operator_message(request)
            set_message(request, "DUT detected. USB boot mode is held.", "Install DUT")
            print(f"DUT detected after {elapsed_s:.1f} s", flush=True)
            return True

        elapsed_s = time.monotonic() - started_at
        heartbeat_s = int(elapsed_s // DUT_WAIT_HEARTBEAT_S)
        if heartbeat_s > last_heartbeat_s:
            display.update_waiting_for_dut(elapsed_s)
            last_heartbeat_s = heartbeat_s
        if elapsed_s >= next_log_at_s:
            print(f"Waiting for DUT installation: {elapsed_s:.0f} s", flush=True)
            next_log_at_s += DUT_WAIT_LOG_INTERVAL_S
        time.sleep(poll_s)

    set_measurement(request, "DUT_PRESENT final", "HIGH")
    set_measurement(request, "DUT installation wait", f"{timeout_s:.1f} s")
    return False


def wait_for_dut_not_present(
    request: pytest.FixtureRequest,
    display: object,
    controller: JigGPIOController,
) -> bool:
    if settings.MOCK_GPIO:
        return True
    if controller.is_dut_present():
        set_operator_message(
            request,
            DUT_PRESENT_WAIT_MESSAGE,
            "DUT_PRESENT LOW",
        )
        display.show_remove_compute_module()
        set_measurement(request, "DUT_PRESENT initial", "LOW")

        deadline = time.monotonic() + settings.CM_FLASHER_DUT_PRESENT_TIMEOUT_S
        while controller.is_dut_present() and time.monotonic() < deadline:
            time.sleep(settings.CM_FLASHER_DUT_PRESENT_POLL_S)

        if controller.is_dut_present():
            set_measurement(request, "DUT_PRESENT final", "LOW")
            return False

        clear_operator_message(request)
        set_message(request, "DUT_PRESENT is HIGH", "RaspberryPi init")
        display.terminal_log("DUT_PRESENT HIGH")

    set_measurement(request, "DUT_PRESENT final", "HIGH")
    return True
