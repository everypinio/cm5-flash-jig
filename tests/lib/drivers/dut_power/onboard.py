from __future__ import annotations

import time
from typing import Any

from .interfaces import DutPowerCapabilities


class OnboardIna229DutPower:
    """Rev.2 DUT power switch controlled by GPIO20 and monitored by INA229."""

    ALERT_CLEAR_TIMEOUT_S = 0.1
    ALERT_CLEAR_POLL_S = 0.002

    backend_name = "onboard_ina229"
    capabilities = DutPowerCapabilities(
        programmable_voltage=False,
        programmable_current_limit=True,
        hardware_overcurrent_trip=True,
    )

    def __init__(
        self,
        gpio_controller: Any,
        monitor: Any,
        *,
        nominal_voltage_v: float = 5.0,
        maximum_current_a: float = 3.0,
    ) -> None:
        self.gpio = gpio_controller
        self.monitor = monitor
        self.nominal_voltage_v = nominal_voltage_v
        self.maximum_current_a = maximum_current_a
        self._connected = False
        self._prepared = False
        self._current_limit_a = maximum_current_a

    def connect(self) -> None:
        if self._connected:
            return
        # Fail safe before opening or configuring the measurement interface.
        self.gpio.set_dut_power_enabled(False)
        self._set_mock_output_state(False)
        try:
            self.monitor.connect()
            self.monitor.configure(current_limit_a=self.maximum_current_a)
            self._connected = True
        except Exception:
            self.gpio.set_dut_power_enabled(False)
            self.monitor.close()
            raise

    def disconnect(self) -> None:
        try:
            self.disable()
        finally:
            self.monitor.close()
            self._connected = False
            self._prepared = False

    def identity(self) -> str:
        self._require_connected()
        return self.monitor.identify()

    def prepare(self, *, voltage_v: float, current_limit_a: float) -> None:
        self._require_connected()
        if abs(voltage_v - self.nominal_voltage_v) > 0.01:
            raise ValueError(
                f"Onboard DUT supply is fixed at {self.nominal_voltage_v:g} V; "
                f"requested {voltage_v:g} V"
            )
        if current_limit_a <= 0 or current_limit_a > self.maximum_current_a:
            raise ValueError(
                f"Onboard DUT current limit must be within "
                f"0..{self.maximum_current_a:g} A"
            )

        self.disable()
        # Clear a previous latched alert only while OUT_EN is safely low.
        self._clear_latched_alert()
        self.monitor.set_overcurrent_limit(current_limit_a)
        self._current_limit_a = current_limit_a
        self._prepared = True

        if self.has_fault():
            raise RuntimeError(
                "INA229 reports a fault after configuration; DUT power remains disabled"
            )

    def enable(self) -> None:
        self._require_connected()
        if not self._prepared:
            raise RuntimeError("DUT power must be prepared before it can be enabled")
        if self.has_fault():
            raise RuntimeError("INA229 ALERT is active; DUT power remains disabled")
        self.gpio.set_dut_power_enabled(True)
        self._set_mock_output_state(True)

    def disable(self) -> None:
        self.gpio.set_dut_power_enabled(False)
        self._set_mock_output_state(False)

    def is_enabled(self) -> bool:
        return self.gpio.is_dut_power_enabled() and not self.has_fault()

    def read_voltage(self) -> float:
        self._require_connected()
        return self.monitor.read_bus_voltage()

    def read_current(self) -> float:
        self._require_connected()
        return self.monitor.read_current()

    def has_fault(self) -> bool:
        self._require_connected()
        if self.gpio.is_dut_power_fault_active():
            self.disable()
            return True
        if self.monitor.has_fault():
            self.disable()
            return True
        return False

    def diagnostics(self) -> dict[str, str | int | float | bool]:
        self._require_connected()
        # DIAG_ALRT read clears latched alerts. Never read it while OUT_EN is
        # high and ALERT is asserted, otherwise the hardware gate could reopen.
        if self.gpio.is_dut_power_fault_active():
            self.disable()
        diagnostics = dict(self.monitor.read_diagnostics())
        diagnostics.update(
            {
                "backend": self.backend_name,
                "out_en": self.gpio.is_dut_power_enabled(),
                "alert_active": self.gpio.is_dut_power_fault_active(),
                "current_limit_a": self._current_limit_a,
            }
        )
        return diagnostics

    def _set_mock_output_state(self, enabled: bool) -> None:
        setter = getattr(self.monitor, "set_output_enabled", None)
        if setter is not None:
            setter(enabled)

    def _clear_latched_alert(self) -> None:
        """Clear INA229 latch and allow its active-low ALERT pin to release."""
        self.monitor.read_diagnostics()
        deadline = time.monotonic() + self.ALERT_CLEAR_TIMEOUT_S
        while self.gpio.is_dut_power_fault_active():
            if time.monotonic() >= deadline:
                return
            time.sleep(self.ALERT_CLEAR_POLL_S)

    def _require_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("Onboard DUT power subsystem is not connected")
