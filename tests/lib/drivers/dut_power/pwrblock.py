from __future__ import annotations

from typing import Any

from .interfaces import DutPowerCapabilities


class PwrBlockDutPower:
    """Compatibility adapter exposing a PwrBlock as a DUT power subsystem."""

    backend_name = "pwrblock"
    capabilities = DutPowerCapabilities(
        programmable_voltage=True,
        programmable_current_limit=True,
        hardware_overcurrent_trip=True,
    )

    def __init__(self, driver: Any, *, channel: int = 0) -> None:
        self.driver = driver
        self.channel = channel
        self._enabled = False
        self._prepared_voltage_v = 0.0
        self._prepared_current_a = 0.0

    def connect(self) -> None:
        self.driver.connect()

    def disconnect(self) -> None:
        try:
            self.disable()
        finally:
            self.driver.disconnect()

    def identity(self) -> str:
        return self.driver.get_uid()

    def prepare(self, *, voltage_v: float, current_limit_a: float) -> None:
        self.driver.set_voltage(self.channel, voltage_v)
        self.driver.set_current(self.channel, current_limit_a)
        self._prepared_voltage_v = self.driver.get_voltage_setpoint(self.channel)
        self._prepared_current_a = self.driver.get_current_setpoint(self.channel)

    def enable(self) -> None:
        self.driver.set_supply(self.channel, "ON")
        self._enabled = True

    def disable(self) -> None:
        self.driver.set_supply(self.channel, "OFF")
        self._enabled = False

    def is_enabled(self) -> bool:
        return self._enabled

    def read_voltage(self) -> float:
        return self.driver.get_voltage(self.channel)

    def read_current(self) -> float:
        return self.driver.get_current(self.channel)

    def has_fault(self) -> bool:
        return False

    def diagnostics(self) -> dict[str, str | int | float | bool]:
        diagnostics: dict[str, str | int | float | bool] = {
            "backend": self.backend_name,
            "channel": self.channel,
            "enabled": self._enabled,
            "voltage_setpoint_v": self._prepared_voltage_v,
            "current_limit_a": self._prepared_current_a,
        }
        try:
            diagnostics["scpi_error"] = self.driver.query_raw("SYST:ERR?")
        except Exception as exc:
            diagnostics["scpi_error"] = f"unavailable: {exc}"
        return diagnostics
