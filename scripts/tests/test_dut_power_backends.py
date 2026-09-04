from __future__ import annotations

import pytest

from tests.lib.drivers.dut_power.onboard import OnboardIna229DutPower
from tests.lib.drivers.dut_power.pwrblock import PwrBlockDutPower
from tests.lib.drivers.ina229 import MockINA229


class FakeGPIOController:
    def __init__(self) -> None:
        self.out_en = True
        self.alert_active = False

    def set_dut_power_enabled(self, enabled: bool) -> None:
        self.out_en = enabled

    def is_dut_power_enabled(self) -> bool:
        return self.out_en

    def is_dut_power_fault_active(self) -> bool:
        return self.alert_active


class DelayedAlertReleaseGPIO(FakeGPIOController):
    def __init__(self, active_reads: int) -> None:
        super().__init__()
        self.active_reads = active_reads

    def is_dut_power_fault_active(self) -> bool:
        if self.active_reads > 0:
            self.active_reads -= 1
            return True
        return False


class FakePwrBlock:
    def __init__(self) -> None:
        self.connected = False
        self.enabled = False
        self.voltage = 0.0
        self.current = 0.0

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def get_uid(self) -> str:
        return "FAKE PWRBLOCK"

    def set_voltage(self, channel: int, value: float) -> None:
        self.voltage = value

    def set_current(self, channel: int, value: float) -> None:
        self.current = value

    def get_voltage_setpoint(self, channel: int) -> float:
        return self.voltage

    def get_current_setpoint(self, channel: int) -> float:
        return self.current

    def set_supply(self, channel: int, state: str) -> None:
        self.enabled = state == "ON"

    def get_voltage(self, channel: int) -> float:
        return self.voltage if self.enabled else 0.0

    def get_current(self, channel: int) -> float:
        return self.current / 2 if self.enabled else 0.0

    def query_raw(self, command: str) -> str:
        return "0,No error"


def test_onboard_backend_starts_safe_and_requires_prepare() -> None:
    gpio = FakeGPIOController()
    monitor = MockINA229()
    power = OnboardIna229DutPower(gpio, monitor)

    power.connect()

    assert not gpio.out_en
    with pytest.raises(RuntimeError, match="prepared"):
        power.enable()

    power.prepare(voltage_v=5.0, current_limit_a=3.0)
    power.enable()
    assert gpio.out_en
    assert power.read_voltage() == 5.0

    power.disconnect()
    assert not gpio.out_en


def test_onboard_backend_does_not_enable_during_alert() -> None:
    gpio = FakeGPIOController()
    monitor = MockINA229()
    power = OnboardIna229DutPower(gpio, monitor)
    power.connect()
    power.prepare(voltage_v=5.0, current_limit_a=3.0)
    gpio.alert_active = True

    with pytest.raises(RuntimeError, match="ALERT"):
        power.enable()

    assert not gpio.out_en


def test_onboard_backend_waits_for_latched_alert_to_release() -> None:
    gpio = DelayedAlertReleaseGPIO(active_reads=2)
    power = OnboardIna229DutPower(gpio, MockINA229())
    power.connect()

    power.prepare(voltage_v=5.0, current_limit_a=3.0)
    power.enable()

    assert gpio.out_en


def test_onboard_backend_disables_before_clearing_latched_diagnostics() -> None:
    gpio = FakeGPIOController()
    monitor = MockINA229()
    power = OnboardIna229DutPower(gpio, monitor)
    power.connect()
    power.prepare(voltage_v=5.0, current_limit_a=3.0)
    power.enable()
    gpio.alert_active = True

    diagnostics = power.diagnostics()

    assert not gpio.out_en
    assert diagnostics["alert_active"] is True


def test_onboard_backend_rejects_non_fixed_voltage() -> None:
    power = OnboardIna229DutPower(FakeGPIOController(), MockINA229())
    power.connect()

    with pytest.raises(ValueError, match="fixed at 5 V"):
        power.prepare(voltage_v=3.3, current_limit_a=1.0)


def test_pwrblock_adapter_preserves_programmable_supply_behaviour() -> None:
    driver = FakePwrBlock()
    power = PwrBlockDutPower(driver, channel=1)

    power.connect()
    power.prepare(voltage_v=5.0, current_limit_a=3.0)
    power.enable()

    assert power.identity() == "FAKE PWRBLOCK"
    assert power.read_voltage() == 5.0
    assert power.read_current() == 1.5

    power.disconnect()
    assert not driver.enabled
    assert not driver.connected
