from __future__ import annotations

import time
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tests.env import settings
from tests.imports import load_flasher_module
from tests.lib.drivers.display.dfr0997_operator_panel import DFR0997OperatorPanel
from tests.lib.drivers.flasher.mock import get_mock_block_device
from tests.lib.drivers.jig_gpio import JigGPIOController
from tests.lib.drivers.jig_gpio.constants import DUT_PRESENT
from tests.lib.hardpy_helpers.cm5_hardpy_dut_info import set_dut_metadata_from_boot_info
from tests.lib.hardpy_helpers.messages import (
    fail_with_operator_message,
    set_message,
)
from tests.lib.hardpy_helpers.reports import set_measurement, set_numeric_measurement
from tests.lib.hardpy_helpers.utils import _hardpy_enabled
from tests.lib.utils.cm5_boot_info import (
    DUT_INFO_FIELDS,
    infer_cm5_part_number,
    parse_boot_info,
)
from tests.lib.utils.dut_presence import wait_for_dut_present
from tests.lib.utils.rpiboot_runner import RpibootRunner
from tests.lib.utils.uart_log_capture import UartLogCapture
from tests.utils import image_path

pytestmark = [
    pytest.mark.module_name("2. CM5 - Flashing"),
    pytest.mark.critical,
    pytest.mark.hold_power_for_module,
]

DETECTED_DUT_DEVICE: str | None = None
UART_BOOT_LOG: str | None = None
RPIBOOT_OUTPUT: str | None = None

USB_BOOT_MILESTONES = (
    ("BOOTSYS", "RPi: BOOTSYS release"),
    ("RPIBOOT", "RPi: RPIBOOT release"),
    ("USB boot mode", "Boot mode: RPIBOOT"),
    ("Linux kernel", "Linux version"),
    ("CM5 model", "Machine model:"),
    ("eMMC detected", "mmcblk0:"),
    ("USB mass-storage gadget", "Mass storage gadget init complete"),
)

def _target_device_path() -> Path | None:
    if DETECTED_DUT_DEVICE:
        return Path(DETECTED_DUT_DEVICE)
    return settings.CM_FLASHER_DEVICE


def _wait_for_new_disk_while_rpiboot_runs(
    flasher: Any | ModuleType,
    before_paths: set[str],
    runner: RpibootRunner,
    *,
    timeout_s: int,
    poll_s: float,
):
    deadline = time.monotonic() + timeout_s
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            devices = flasher.list_block_devices()
            candidates = [
                device
                for device in devices
                if device.kind == "disk"
                and device.path not in before_paths
                and not device.has_mounts
                and not device.path.startswith("/dev/loop")
                and not device.path.startswith("/dev/zram")
            ]
            if len(candidates) == 1:
                return candidates[0]
            if len(candidates) > 1:
                details = "\n".join(
                    f"- {flasher.describe_device(device)}" for device in candidates
                )
                raise RuntimeError(
                    f"More than one new disk appeared. Refusing to guess:\n{details}"
                )
        except Exception as exc:
            last_error = exc

        code = runner.poll()
        if code not in {None, 0}:
            output = runner.output_text().strip()
            raise RuntimeError(f"rpiboot exited with code {code}: {output}")

        time.sleep(poll_s)

    suffix = f" Last polling error: {last_error}" if last_error else ""
    output = runner.output_text().strip()
    raise RuntimeError(
        f"Timed out waiting for DUT USB mass-storage disk while rpiboot was running.{suffix}\n"
        f"rpiboot output:\n{output}"
    )


def _write_usb_boot_log(log_text: str) -> Path:
    log_dir = Path(settings.DUT_USB_BOOT_LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = log_dir / f"dut_usb_boot_{stamp}.log"
    path.write_text(log_text, encoding="utf-8", errors="replace")
    return path.resolve()


def _write_rpiboot_log(log_text: str) -> Path:
    log_dir = Path(settings.DUT_USB_BOOT_LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = log_dir / f"rpiboot_{stamp}.log"
    path.write_text(log_text, encoding="utf-8", errors="replace")
    return path.resolve()


def _report_usb_boot_log(
    request: pytest.FixtureRequest,
    display: object,
    boot_log: str,
) -> None:
    for label, needle in USB_BOOT_MILESTONES:
        if needle in boot_log:
            display.terminal_log(label)
            set_message(request, f"USB boot: {label}", "USB boot")
            set_measurement(request, f"usb boot milestone {label}", "seen")


def _record_usb_boot_log(
    request: pytest.FixtureRequest,
    *,
    log_text: str,
    target_path: str | None,
    rpiboot_output: str,
) -> tuple[Path, dict[str, str], dict[str, object]]:
    log_path = _write_usb_boot_log(log_text)
    boot_info = parse_boot_info(log_text)
    variant_info = infer_cm5_part_number(log_text)

    if _hardpy_enabled(request):
        import hardpy

        set_dut_metadata_from_boot_info(boot_info, variant_info)
        hardpy.set_case_artifact(
            {
                "artifact_type": "dut_usb_boot_log",
                "target_disk": target_path,
                "dut_info": {
                    name: boot_info.get(name, "not found") for name in DUT_INFO_FIELDS
                },
                "cm5_variant": variant_info,
                "rpiboot_output": rpiboot_output,
                "log_path": str(log_path),
                "log_text": log_text,
            }
        )

    set_measurement(request, "DUT USB boot log path", str(log_path))
    set_numeric_measurement(
        request, "DUT USB boot log bytes", float(len(log_text.encode("utf-8"))), "B"
    )
    for name in DUT_INFO_FIELDS:
        set_measurement(
            request, f"DUT USB boot {name}", boot_info.get(name, "not found")
        )
    for name, value in variant_info.items():
        set_measurement(request, f"DUT USB boot CM5 {name}", str(value))

    return log_path, boot_info, variant_info


@pytest.mark.case_name("2.1. Execute USB boot")
def test_usb_boot_execution(
    request: pytest.FixtureRequest, display_panel: DFR0997OperatorPanel, gpio_controller: JigGPIOController, dut_power
) -> None:
    global DETECTED_DUT_DEVICE, UART_BOOT_LOG, RPIBOOT_OUTPUT

    set_message(
        request,
        "Starting rpiboot and waiting for DUT disk",
        "USB boot",
    )

    flasher = load_flasher_module(request)
    if not flasher:
        raise Exception("No Flasher module")

    voltage = settings.DUT_POWER_NOMINAL_V
    current = settings.DUT_POWER_CURRENT_LIMIT_A
    power_settle_s = settings.DUT_USB_BOOT_POWER_SETTLE_S
    uart_device = settings.CM_FLASHER_UART_DEVICE
    uart_baud = settings.CM_FLASHER_UART_BAUD
    uart_post_capture_s = settings.DUT_USB_BOOT_UART_POST_CAPTURE_S
    rpiboot_timeout_s = settings.CM_FLASHER_RPIBOOT_TIMEOUT_S
    device_timeout_s = settings.CM_FLASHER_DEVICE_TIMEOUT_S
    device_poll_s = settings.CM_FLASHER_DEVICE_POLL_S
    rpiboot_output = ""
    boot_log = ""
    uart_capture: UartLogCapture | None = None
    target_path: str | None = None
    runner: RpibootRunner | None = None

    try:
        display_panel.terminal_start("USB boot")
        display_panel.terminal_log("Listing current disks")
        before = flasher.list_block_devices()
        before_paths = {device.path for device in before if device.kind == "disk"}
        set_measurement(
            request, "block disks before rpiboot", str(len(before_paths))
        )

        if settings.CM_FLASHER_SKIP_RPIBOOT:
            display_panel.terminal_log("Using existing USB disk")
            target = flasher.choose_existing_usb_disk(flasher.list_block_devices())
            target_path = target.path
        else:
            if not settings.CM_FLASHER_ENABLE_POWER_WRITE:
                fail_with_operator_message(
                    request,
                    "Set CM_FLASHER_ENABLE_POWER_WRITE=1 to allow this test to power-cycle DUT",
                    "USB boot",
                )

            dut_power.disable()
            set_measurement(request, "DUT power before USB boot", "OFF")
            display_panel.terminal_log("DUT power OFF")

            assert wait_for_dut_present(request, display_panel, gpio_controller), (
                f"DUT_PRESENT on GPIO{DUT_PRESENT} stayed HIGH after waiting for "
                f"{settings.CM_FLASHER_DUT_PRESENT_TIMEOUT_S} s"
            )
            gpio_controller.set_boot_mode(True)
            time.sleep(0.1)
            boot_active = gpio_controller.is_boot_mode_active()
            set_measurement(
                request, "nRPI_BOOT", "LOW" if boot_active else "HIGH"
            )
            if not boot_active:
                fail_with_operator_message(
                    request,
                    "nRPI_BOOT readback stayed HIGH after write LOW",
                    "USB boot",
                )
            display_panel.terminal_log("nRPI_BOOT LOW")

            set_measurement(request, "DUT USB boot UART device", str(uart_device))
            set_numeric_measurement(
                request, "DUT USB boot UART baud", float(uart_baud), "baud"
            )
            display_panel.terminal_log("UART log capture")
            uart_capture = UartLogCapture(uart_device, uart_baud).start()
            dut_power.prepare(voltage_v=voltage, current_limit_a=current)
            dut_power.enable()
            set_measurement(request, "DUT power during USB boot", "ON")
            display_panel.terminal_log("DUT power ON")
            time.sleep(power_settle_s)

            if settings.MOCK_FLASHING:
                display_panel.terminal_log("Mocking rpiboot")
                target = get_mock_block_device()
                target_path = target.path
                rpiboot_output = "Sending bootcode.bin... Successful"
            else:
                display_panel.terminal_log("Running rpiboot")
                runner = RpibootRunner(
                    settings.CM_FLASHER_RPIBOOT_COMMAND,
                    use_sudo=not settings.CM_FLASHER_NO_RPIBOOT_SUDO,
                    boot_dir=settings.CM_FLASHER_RPIBOOT_DIR,
                )
                with runner as rpiboot:
                    display_panel.terminal_log("Waiting for DUT disk")
                    target = _wait_for_new_disk_while_rpiboot_runs(
                        flasher,
                        before_paths,
                        rpiboot,
                        timeout_s=max(rpiboot_timeout_s, device_timeout_s),
                        poll_s=device_poll_s,
                    )
                    target_path = target.path
                    rpiboot_output = rpiboot.output_text()
            time.sleep(uart_post_capture_s)

        flasher.validate_target_device(target)
        DETECTED_DUT_DEVICE = target.path
        set_measurement(request, "DUT target disk", str(target.path))
        set_measurement(
            request, "DUT target description", str(flasher.describe_device(target))
        )
        display_panel.terminal_log(f"Target: {target.path}")

        if uart_capture is not None:
            boot_log = uart_capture.stop()
            uart_capture = None
            display_panel.terminal_log("USB boot log captured")
            
        UART_BOOT_LOG = boot_log
        RPIBOOT_OUTPUT = rpiboot_output
    except Exception as exc:
        if runner is not None:
            rpiboot_output = runner.output_text()
        if uart_capture is not None:
            boot_log = uart_capture.stop()
            uart_capture = None

        UART_BOOT_LOG = boot_log
        RPIBOOT_OUTPUT = rpiboot_output
        try:
            uart_log_path = _write_usb_boot_log(boot_log)
            rpiboot_log_path = _write_rpiboot_log(rpiboot_output)
        except Exception as log_exc:
            log_details = f"\nFailed to persist diagnostic logs: {log_exc}"
        else:
            set_measurement(
                request, "DUT USB boot failure UART log", str(uart_log_path)
            )
            set_measurement(
                request, "DUT USB boot failure rpiboot log", str(rpiboot_log_path)
            )
            set_numeric_measurement(
                request,
                "DUT USB boot failure UART log bytes",
                float(len(boot_log.encode("utf-8"))),
                "B",
            )
            set_numeric_measurement(
                request,
                "DUT USB boot failure rpiboot log bytes",
                float(len(rpiboot_output.encode("utf-8"))),
                "B",
            )
            log_details = (
                f"\nUART log: {uart_log_path}"
                f"\nrpiboot log: {rpiboot_log_path}"
            )
        set_message(request, f"USB boot failed: {exc}{log_details}", "USB boot")
        raise
    finally:
        if uart_capture is not None:
            uart_capture.stop()


@pytest.mark.case_name("2.2. Analyze USB boot logs")
def test_usb_boot_log_analysis(
    request: pytest.FixtureRequest, display_panel: DFR0997OperatorPanel
) -> None:
    global DETECTED_DUT_DEVICE, UART_BOOT_LOG, RPIBOOT_OUTPUT

    set_message(
        request,
        "Analyzing USB boot logs",
        "USB boot",
    )

    if UART_BOOT_LOG is None:
        pytest.skip("No UART boot log available to analyze.")

    boot_log = UART_BOOT_LOG
    rpiboot_output = RPIBOOT_OUTPUT or ""
    target_path = DETECTED_DUT_DEVICE

    display_panel.terminal_start("USB boot log")
    try:
        _report_usb_boot_log(request, display_panel, boot_log)
        _record_usb_boot_log(
            request,
            log_text=boot_log,
            target_path=target_path,
            rpiboot_output=rpiboot_output,
        )
        display_panel.terminal_log("USB boot log analyzed")
    except Exception as exc:
        set_message(request, f"USB boot log analysis failed: {exc}", "USB boot log")
        raise


@pytest.mark.case_name("2.3. Flash image to DUT eMMC")
def test_flash_emmc(
    request: pytest.FixtureRequest, display_panel: DFR0997OperatorPanel
) -> None:
    set_message(
        request,
        "Writing image to DUT eMMC",
        "Flash image",
    )

    flasher = load_flasher_module(request)
    if not flasher:
        raise Exception("No Flasher module")
    image = image_path()
    target_path = _target_device_path()

    try:
        display_panel.terminal_start("Flash image")
        display_panel.show_flashing()
        set_measurement(request, "image path", str(image))
        if not image.exists():
            fail_with_operator_message(
                request, f"Image file does not exist: {image}", "Flash image"
            )
        if not image.is_file():
            fail_with_operator_message(
                request, f"Image path is not a file: {image}", "Flash image"
            )

        if not target_path:
            fail_with_operator_message(
                request,
                "DUT target disk is unknown. Run USB boot discovery or set CM_FLASHER_DEVICE.",
                "Flash image",
            )

        if not settings.CM_FLASHER_ENABLE_FLASH_WRITE:
            fail_with_operator_message(
                request,
                "Set CM_FLASHER_ENABLE_FLASH_WRITE=1 to allow writing DUT eMMC",
                "Flash image",
            )

        current = flasher.list_block_devices()
        target = flasher.disk_by_path(current, target_path)
        if target is None:
            fail_with_operator_message(
                request, f"Target disk was not found: {target_path}", "Flash image"
            )
            return

        flasher.validate_target_device(target)
        set_measurement(request, "flash target disk", str(target.path))
        set_measurement(
            request, "flash target description", str(flasher.describe_device(target))
        )
        display_panel.terminal_log(f"Target: {target.path}")

        if target.has_mounts:
            if settings.CM_FLASHER_KEEP_MOUNTED:
                fail_with_operator_message(
                    request,
                    f"Target has mounted filesystems: {target.child_mountpoints}",
                    "Flash image",
                )
            display_panel.terminal_log("Unmounting target")
            flasher.unmount_device(target, dry_run=False)

        display_panel.terminal_log("Writing image")
        flasher.write_image(image, target, dry_run=False)
        set_measurement(request, "image write", "completed")
        display_panel.terminal_log("Write completed")
    except Exception as exc:
        set_message(request, f"Image write failed: {exc}", "Flash image")
        raise
