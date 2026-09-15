from __future__ import annotations

import pytest

from tests.lib.drivers.ina229 import INA229


class FakeSPI:
    def __init__(self) -> None:
        self.mode = 0
        self.max_speed_hz = 0
        self.bits_per_word = 0
        self.opened: tuple[int, int] | None = None
        self.closed = False
        self.frames: list[list[int]] = []
        self.registers = {
            INA229.MANUFACTURER_ID: INA229.EXPECTED_MANUFACTURER_ID,
            INA229.DEVICE_ID: (INA229.EXPECTED_DIE_ID << 4) | 1,
            INA229.DIAG_ALRT: 0x0001,
        }

    def open(self, bus: int, device: int) -> None:
        self.opened = (bus, device)

    def close(self) -> None:
        self.closed = True

    def xfer2(self, data: list[int]) -> list[int]:
        self.frames.append(list(data))
        command = data[0]
        register = command >> 2
        is_read = bool(command & 1)
        if is_read:
            length = len(data) - 1
            value = self.registers.get(register, 0)
            return [0] + list(value.to_bytes(length, "big"))

        value = int.from_bytes(bytes(data[1:]), "big")
        if register == INA229.CONFIG and value & (1 << 15):
            self.registers[INA229.CONFIG] = 0
            self.registers[INA229.DIAG_ALRT] = 1
        else:
            self.registers[register] = value
        return [0] * len(data)


def make_monitor(spi: FakeSPI) -> INA229:
    return INA229(
        bus=0,
        device=1,
        shunt_ohms=0.01,
        max_current_a=3.0,
        adc_range=0,
        conversion_time_code=3,
        spi=spi,
    )


def test_configure_programs_calibration_and_overcurrent_threshold() -> None:
    spi = FakeSPI()
    monitor = make_monitor(spi)

    monitor.connect()
    monitor.configure(current_limit_a=3.0)

    assert spi.opened == (0, 1)
    assert spi.mode == 1
    assert spi.registers[INA229.SHUNT_CAL] == 750
    assert spi.registers[INA229.SOVL] == 6000
    assert spi.registers[INA229.ADC_CONFIG] == 0xB6D8
    assert spi.registers[INA229.DIAG_ALRT] == 0x8001
    assert monitor.identify() == "TI INA229 rev.1"


def test_measurement_register_conversion() -> None:
    spi = FakeSPI()
    monitor = make_monitor(spi)
    monitor.connect()
    monitor.configure(current_limit_a=3.0)

    bus_raw = round(5.0 / INA229.BUS_VOLTAGE_LSB_V)
    current_raw = 1 << 18
    spi.registers[INA229.VBUS] = bus_raw << 4
    spi.registers[INA229.CURRENT] = current_raw << 4

    assert monitor.read_bus_voltage() == pytest.approx(5.0, abs=0.0002)
    assert monitor.read_current() == pytest.approx(1.5)


def test_identify_rejects_wrong_device() -> None:
    spi = FakeSPI()
    spi.registers[INA229.DEVICE_ID] = 0x1231
    monitor = make_monitor(spi)
    monitor.connect()

    with pytest.raises(RuntimeError, match="die ID"):
        monitor.identify()


def test_spi_read_command_contains_six_bit_address_and_read_bit() -> None:
    spi = FakeSPI()
    monitor = make_monitor(spi)
    monitor.connect()

    monitor.read_u16(INA229.MANUFACTURER_ID)

    assert spi.frames[-1] == [0xF9, 0x00, 0x00]
