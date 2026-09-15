import os
import select
import termios
import time
from pathlib import Path

import pytest

from tests.env import settings
from tests.lib.hardpy_helpers.messages import set_message
from tests.lib.utils.uart_log_capture import _configure_uart, _prepare_uart_device
from tests.utils import (
    set_measurement,
)

BOOT_MILESTONES = (
    ("RPi bootloader", "RPi: BOOTLOADER release"),
    ("Linux kernel", "Linux version"),
    ("CM5 model", "Machine model:"),
    ("eMMC detected", "mmcblk0:"),
    ("rootfs mounted", "mounted filesystem"),
    ("systemd", "systemd[1]: systemd"),
    ("serial login", settings.DUT_BOOT_SUCCESS_PHRASE),
)


BOOT_FATAL_PATTERNS = (
    "Kernel panic",
    "Unable to mount root fs",
    "No working init",
    "emergency mode",
    "Timed out waiting",
)


def open_uart(device: Path, baud: int) -> int:
    if settings.MOCK_FLASHING:
        return -1
    _prepare_uart_device(device)
    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        _configure_uart(fd, baud)
        termios.tcflush(fd, termios.TCIOFLUSH)
        return fd
    except Exception:
        os.close(fd)
        raise


def read_uart_boot_log(
    fd: int,
    *,
    timeout_s: float,
    success_phrase: str,
    display: object,
    request: pytest.FixtureRequest,
) -> tuple[str, bool, list[str]]:
    chunks: list[bytes] = []
    text_seen = ""
    milestones_seen: set[str] = set()
    fatal_matches: list[str] = []
    deadline = time.monotonic() + timeout_s

    while time.monotonic() < deadline:
        remaining = max(0.0, deadline - time.monotonic())
        if fd == -1:
            data = b"RPi: BOOTLOADER release\nLinux version\nMachine model:\nmmcblk0:\nmounted filesystem\nsystemd[1]: systemd\n" + success_phrase.encode() + b"\n"
        else:
            readable, _, _ = select.select([fd], [], [], min(0.25, remaining))
            if not readable:
                continue

            try:
                data = os.read(fd, 4096)
            except BlockingIOError:
                continue
            if not data:
                continue

        chunks.append(data)
        text_seen += data.decode("utf-8", errors="replace")

        for label, needle in BOOT_MILESTONES:
            if label not in milestones_seen and needle in text_seen:
                milestones_seen.add(label)
                display.terminal_log(label)
                set_message(request, f"Boot: {label}", "Boot check")
                set_measurement(request, f"boot milestone {label}", "seen")

        for pattern in BOOT_FATAL_PATTERNS:
            if pattern in text_seen and pattern not in fatal_matches:
                fatal_matches.append(pattern)

        if success_phrase in text_seen:
            return text_seen, True, fatal_matches
            
        if fd == -1:
            break

    return b"".join(chunks).decode("utf-8", errors="replace"), False, fatal_matches


def write_boot_log(log_text: str) -> Path:
    log_dir = Path(settings.DUT_BOOT_LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = log_dir / f"dut_boot_{stamp}.log"
    path.write_text(log_text, encoding="utf-8", errors="replace")
    return path.resolve()
