import os
from pathlib import Path
import select
import subprocess
import termios
import threading

from tests.env import settings



def _baud_constant(baud: int) -> int:
    value = getattr(termios, f"B{baud}", None)
    if value is None:
        raise RuntimeError(f"Unsupported UART baud rate: {baud}")
    return value


def _configure_uart(fd: int, baud: int) -> None:
    attrs = termios.tcgetattr(fd)
    baud_flag = _baud_constant(baud)
    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = termios.CLOCAL | termios.CREAD | termios.CS8
    attrs[3] = 0
    attrs[4] = baud_flag
    attrs[5] = baud_flag
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 0
    crtscts = getattr(termios, "CRTSCTS", 0)
    if crtscts:
        attrs[2] &= ~crtscts
    termios.tcsetattr(fd, termios.TCSANOW, attrs)


def _prepare_uart_device(device: Path) -> None:
    if os.access(device, os.R_OK | os.W_OK):
        return

    try:
        subprocess.run(
            ["sudo", "-n", "chgrp", "dialout", str(device)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["sudo", "-n", "chmod", "0660", str(device)],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PermissionError(
            f"UART device {device} is not accessible. Run the UART udev setup "
            "or allow passwordless sudo for chgrp/chmod on the UART device."
        ) from exc


class UartLogCapture:
    def __init__(self, device: Path, baud: int) -> None:
        self.device = device
        self.baud = baud
        self.fd: int | None = None
        self._chunks: list[bytes] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> "UartLogCapture":
        if settings.MOCK_FLASHING:
            return self

        _prepare_uart_device(self.device)
        self.fd = os.open(self.device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        _configure_uart(self.fd, self.baud)
        termios.tcflush(self.fd, termios.TCIOFLUSH)
        self._thread = threading.Thread(
            target=self._run, name="dut-usb-boot-uart", daemon=True
        )
        self._thread.start()
        return self

    def stop(self) -> str:
        if settings.MOCK_FLASHING:
            return "Mock UART Boot Log\nraspberrypi login:\n"

        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        return self.text()

    def text(self) -> str:
        return b"".join(self._chunks).decode("utf-8", errors="replace")

    def _run(self) -> None:
        assert self.fd is not None
        while not self._stop.is_set():
            readable, _, _ = select.select([self.fd], [], [], 0.2)
            if not readable:
                continue
            try:
                data = os.read(self.fd, 4096)
            except BlockingIOError:
                continue
            if data:
                self._chunks.append(data)
