"""Simple pyvisa-based driver skeleton for Power Block PSU."""

from __future__ import annotations

import os
import errno
import time
from pathlib import Path
from typing import Optional

import pyvisa


class DirectUsbtmcResource:
    """Minimal SCPI transport for Linux /dev/usbtmcN devices."""

    def __init__(self, path: str, timeout_ms: int) -> None:
        self.path = path
        self.timeout = timeout_ms
        self.read_termination = "\n"
        self.write_termination = "\n"
        flags = os.O_RDWR | os.O_NONBLOCK | getattr(os, "O_NOCTTY", 0)
        self._fd = os.open(path, flags)

    def close(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def write(self, cmd: str) -> None:
        payload = cmd
        if self.write_termination and not payload.endswith(self.write_termination):
            payload += self.write_termination
        os.write(self._fd, payload.encode("ascii"))

    def query(self, cmd: str) -> str:
        self.write(cmd)
        return self._read_response()

    def _read_response(self) -> str:
        deadline = time.monotonic() + (self.timeout / 1000)
        chunks: list[bytes] = []

        while time.monotonic() < deadline:
            try:
                chunk = os.read(self._fd, 4096)
            except BlockingIOError:
                time.sleep(0.02)
                continue
            except OSError as exc:
                if exc.errno in {errno.EAGAIN, errno.EWOULDBLOCK}:
                    time.sleep(0.02)
                    continue
                raise

            if not chunk:
                time.sleep(0.02)
                continue
            chunks.append(chunk)
            if chunk.endswith(b"\n") or chunk.endswith(b"\r"):
                break

        if not chunks:
            raise TimeoutError(f"Timed out reading from {self.path}")

        return b"".join(chunks).decode(errors="replace").strip()


class PowerBlockDriverImpl:
    """Minimal Power Block driver skeleton compatible with current test flow."""

    def __init__(
        self,
        resource_name: Optional[str] = None,
        vid: str = "0xCAFF",
        pid: str = "0x4000",
        timeout_ms: int = 5000,
    ) -> None:
        self.resource_name = resource_name
        self.vid = self._normalize_id(vid)
        self.pid = self._normalize_id(pid)
        self.timeout_ms = timeout_ms
        self._rm: Optional[pyvisa.ResourceManager] = None
        self._inst = None

    @property
    def is_connected(self) -> bool:
        """Return True when instrument session is open."""
        return self._inst is not None

    def connect(self) -> None:
        """Open VISA session to Power Block source."""
        if self._inst is not None:
            return

        target = self.resource_name
        if target is None:
            self._rm = pyvisa.ResourceManager()
            try:
                target = self._find_resource_by_vid_pid()
            except RuntimeError:
                target = self._find_single_usbtmc_device()

        if target.startswith("/dev/usbtmc"):
            target = self._resolve_usbtmc_device(target)
            self._inst = DirectUsbtmcResource(target, self.timeout_ms)
        else:
            if self._rm is None:
                self._rm = pyvisa.ResourceManager()
            self._inst = self._rm.open_resource(target)

        self._inst.timeout = self.timeout_ms

        self._inst.read_termination = "\n"
        self._inst.write_termination = "\n"

    def disconnect(self) -> None:
        """Close VISA session."""
        if self._inst is not None:
            self._inst.close()
            self._inst = None

        if self._rm is not None:
            self._rm.close()
            self._rm = None

    def get_uid(self) -> str:
        """Return instrument identity string."""
        return self._query("*IDN?")

    def query_raw(self, command: str) -> str:
        """Return raw SCPI query response for diagnostics."""
        return self._query(command)

    def write_raw(self, command: str) -> None:
        """Send a raw SCPI command for diagnostics or device-specific setup."""
        self._write(command)

    def set_supply(self, channel: int, state: str) -> None:
        """Enable or disable channel output (expected state: ON/OFF)."""
        self.select_channel(channel)
        state_up = state.strip().upper()
        if state_up not in {"ON", "OFF"}:
            raise ValueError("state must be 'ON' or 'OFF'")
        self._write(f"OUTP {state_up}")

    def select_channel(self, channel: int) -> None:
        """Select output channel when the instrument supports channels."""
        if channel <= 0:
            return
        self._write(f"INST CH{channel}")

    def set_voltage(self, channel: int, value: float) -> None:
        """Set voltage setpoint in volts."""
        self.select_channel(channel)
        self._write(f"VOLT {value:.3f}")

    def set_current(self, channel: int, value: float) -> None:
        """Set current limit in amps."""
        self.select_channel(channel)
        self._write(f"CURR {value:.3f}")

    def get_voltage_setpoint(self, channel: int=0) -> float:
        """Read configured voltage setpoint in volts."""
        self.select_channel(channel)
        return self._query_float_first_supported("VOLT?")

    def get_current_setpoint(self, channel: int=0) -> float:
        """Read configured current limit in amps."""
        self.select_channel(channel)
        return self._query_float_first_supported("CURR?")

    def get_voltage(self, channel: int=0) -> float:
        """Read measured output voltage in volts."""
        self.select_channel(channel)
        return self._query_float_first_supported("MEAS:VOLT?")

    def get_current(self, channel: int=0) -> float:
        """Read measured output current in amps."""
        self.select_channel(channel)
        return self._query_float_first_supported("MEAS:CURR?")

    def _write(self, cmd: str) -> None:
        """Send SCPI command to instrument."""
        if self._inst is None:
            raise RuntimeError("Power Block is not connected")
        self._inst.write(cmd)

    def _query(self, cmd: str) -> str:
        """Send SCPI query and return stripped response."""
        if self._inst is None:
            raise RuntimeError("Power Block is not connected")
        return str(self._inst.query(cmd)).strip()

    def _query_float_first_supported(self, *commands: str) -> float:
        errors: list[str] = []
        for command in commands:
            try:
                response = self._query(command)
                return float(response.replace("\x00", "").strip())
            except Exception as exc:
                errors.append(f"{command}: {exc}")

        details = "; ".join(errors)
        raise RuntimeError(f"Power Block did not return a numeric value. Tried: {details}")

    def _find_resource_by_vid_pid(self) -> str:
        """Find VISA resource name that matches configured USB VID/PID."""
        if self._rm is None:
            raise RuntimeError("VISA resource manager is not initialized")

        resources = self._rm.list_resources()
        for resource in resources:
            if self._resource_matches_vid_pid(resource):
                return resource

        raise RuntimeError(
            f"Power Block not found by VID:PID {self.vid}:{self.pid}. "
            f"Visible VISA resources: {resources}"
        )

    def _find_single_usbtmc_device(self) -> str:
        devices = sorted(Path("/dev").glob("usbtmc*"))
        if len(devices) == 1:
            return str(devices[0])
        if not devices:
            raise RuntimeError(
                "No VISA resource or /dev/usbtmc* device found for Power Block. "
                "Check lsusb, run 'sudo modprobe usbtmc', and reconnect the device."
            )
        details = ", ".join(str(device) for device in devices)
        raise RuntimeError(
            "More than one /dev/usbtmc* device found. Set PWRBLOCK_RESOURCE "
            f"explicitly. Devices: {details}"
        )

    def _resolve_usbtmc_device(self, requested: str) -> str:
        if Path(requested).exists():
            return requested

        fallback = self._find_single_usbtmc_device()
        if fallback != requested:
            return fallback

        raise RuntimeError(f"USBTMC device does not exist: {requested}")

    def _resource_matches_vid_pid(self, resource: str) -> bool:
        """
        Match USB VISA resource strings like:
        USB0::0xCAFF::0x4000::SERIAL::INSTR
        """
        parts = resource.split("::")
        if len(parts) < 3:
            return False
        if not parts[0].upper().startswith("USB"):
            return False

        vendor = self._normalize_id(parts[1])
        product = self._normalize_id(parts[2])
        return vendor == self.vid and product == self.pid

    @staticmethod
    def _normalize_id(value: str) -> str:
        """Normalize VID/PID to lowercase hex without 0x prefix."""
        text = value.strip().lower()
        if text.startswith("0x"):
            return f"{int(text, 16):x}"
        if any(char in "abcdef" for char in text):
            return f"{int(text, 16):x}"
        return f"{int(text, 10):x}"

if __name__ == "__main__":
    pb = PowerBlockDriverImpl()
    pb.connect()
    print(pb.get_uid())
    pb.set_voltage(1, 5)
    pb.set_current(1, 2)
    pb.set_supply(1,"ON")
    print(f"curr:{pb.get_current()}")
    print(f"volt:{pb.get_voltage()}")
    pb.disconnect()
