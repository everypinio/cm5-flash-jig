"""INA229 SPI current/voltage monitor used by the rev.2 flash jig.

Register addresses and conversion factors follow TI INA229 datasheet SLYS023A.
The SPI timing is mode 1: MOSI is sampled on the falling SCLK edge and MISO is
shifted on the rising edge.
"""

from __future__ import annotations

import time
from typing import Protocol, Self


class SPITransport(Protocol):
    mode: int
    max_speed_hz: int
    bits_per_word: int

    def open(self, bus: int, device: int) -> None: ...

    def close(self) -> None: ...

    def xfer2(self, data: list[int]) -> list[int]: ...


class INA229:
    CONFIG = 0x00
    ADC_CONFIG = 0x01
    SHUNT_CAL = 0x02
    VSHUNT = 0x04
    VBUS = 0x05
    CURRENT = 0x07
    DIAG_ALRT = 0x0B
    SOVL = 0x0C
    MANUFACTURER_ID = 0x3E
    DEVICE_ID = 0x3F

    EXPECTED_MANUFACTURER_ID = 0x5449
    EXPECTED_DIE_ID = 0x229
    BUS_VOLTAGE_LSB_V = 195.3125e-6
    SHUNT_VOLTAGE_LSB_V = {0: 312.5e-9, 1: 78.125e-9}
    SOVL_LSB_V = {0: 5e-6, 1: 1.25e-6}

    def __init__(
        self,
        *,
        bus: int = 0,
        device: int = 1,
        max_speed_hz: int = 1_000_000,
        shunt_ohms: float = 0.01,
        max_current_a: float = 3.0,
        adc_range: int = 0,
        conversion_time_code: int = 3,
        spi: SPITransport | None = None,
    ) -> None:
        if shunt_ohms <= 0:
            raise ValueError("INA229 shunt resistance must be positive")
        if max_current_a <= 0:
            raise ValueError("INA229 maximum current must be positive")
        if adc_range not in {0, 1}:
            raise ValueError("INA229 ADC range must be 0 or 1")
        if conversion_time_code not in range(8):
            raise ValueError("INA229 conversion time code must be 0..7")

        self.bus = bus
        self.device = device
        self.max_speed_hz = max_speed_hz
        self.shunt_ohms = shunt_ohms
        self.max_current_a = max_current_a
        self.adc_range = adc_range
        self.conversion_time_code = conversion_time_code
        self._spi = spi
        self._connected = False
        self.current_lsb_a = self.max_current_a / (1 << 19)

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        if self._connected:
            return
        if self._spi is None:
            try:
                import spidev
            except ImportError as exc:
                raise RuntimeError(
                    "spidev is required for the onboard INA229 backend"
                ) from exc
            self._spi = spidev.SpiDev()

        self._spi.open(self.bus, self.device)
        self._spi.mode = 0b01
        self._spi.max_speed_hz = self.max_speed_hz
        self._spi.bits_per_word = 8
        self._connected = True

    def close(self) -> None:
        if self._spi is not None and self._connected:
            self._spi.close()
        self._connected = False

    def identify(self) -> str:
        manufacturer_id = self.read_u16(self.MANUFACTURER_ID)
        device_id = self.read_u16(self.DEVICE_ID)
        die_id = device_id >> 4
        if manufacturer_id != self.EXPECTED_MANUFACTURER_ID:
            raise RuntimeError(
                f"Unexpected INA229 manufacturer ID 0x{manufacturer_id:04X}; "
                f"expected 0x{self.EXPECTED_MANUFACTURER_ID:04X}"
            )
        if die_id != self.EXPECTED_DIE_ID:
            raise RuntimeError(
                f"Unexpected INA229 die ID 0x{die_id:03X}; "
                f"expected 0x{self.EXPECTED_DIE_ID:03X}"
            )
        return f"TI INA229 rev.{device_id & 0xF}"

    def configure(self, *, current_limit_a: float | None = None) -> None:
        self._require_connected()
        limit_a = current_limit_a or self.max_current_a
        if limit_a <= 0 or limit_a > self.max_current_a:
            raise ValueError(
                f"INA229 current limit must be within 0..{self.max_current_a:g} A"
            )

        self.write_u16(self.CONFIG, 1 << 15)
        time.sleep(0.001)
        self.identify()

        config = self.adc_range << 4
        self.write_u16(self.CONFIG, config)

        # Continuous shunt + bus measurement, one sample per result.
        ct = self.conversion_time_code
        adc_config = (0xB << 12) | (ct << 9) | (ct << 6) | (ct << 3)
        self.write_u16(self.ADC_CONFIG, adc_config)

        calibration = self._calibration_value()
        self.write_u16(self.SHUNT_CAL, calibration)
        self.set_overcurrent_limit(limit_a)

        # Latch active-low ALERT. Reading DIAG_ALRT clears a latched event, so
        # the higher-level power controller must force OUT_EN low first.
        self.write_u16(self.DIAG_ALRT, (1 << 15) | 1)

        if self.read_u16(self.CONFIG) != config:
            raise RuntimeError("INA229 CONFIG readback mismatch")
        if self.read_u16(self.SHUNT_CAL) != calibration:
            raise RuntimeError("INA229 SHUNT_CAL readback mismatch")

        diag = self.read_diagnostics()
        if not diag["memory_ok"]:
            raise RuntimeError("INA229 trim-memory checksum error")

    def set_overcurrent_limit(self, current_limit_a: float) -> int:
        if current_limit_a <= 0 or current_limit_a > self.max_current_a:
            raise ValueError(
                f"INA229 current limit must be within 0..{self.max_current_a:g} A"
            )
        threshold_v = current_limit_a * self.shunt_ohms
        raw = round(threshold_v / self.SOVL_LSB_V[self.adc_range])
        if not 0 < raw <= 0x7FFF:
            raise ValueError("INA229 overcurrent threshold is outside SOVL range")
        self.write_u16(self.SOVL, raw)
        if self.read_u16(self.SOVL) != raw:
            raise RuntimeError("INA229 SOVL readback mismatch")
        return raw

    def read_bus_voltage(self) -> float:
        raw = self.read_u24(self.VBUS) >> 4
        return raw * self.BUS_VOLTAGE_LSB_V

    def read_shunt_voltage(self) -> float:
        raw = self._signed(self.read_u24(self.VSHUNT) >> 4, 20)
        return raw * self.SHUNT_VOLTAGE_LSB_V[self.adc_range]

    def read_current(self) -> float:
        raw = self._signed(self.read_u24(self.CURRENT) >> 4, 20)
        return raw * self.current_lsb_a

    def read_diagnostics(self) -> dict[str, bool | int]:
        raw = self.read_u16(self.DIAG_ALRT)
        return {
            "raw": raw,
            "alert_latched": bool(raw & (1 << 15)),
            "conversion_ready_alert": bool(raw & (1 << 14)),
            "alert_active_high": bool(raw & (1 << 12)),
            "memory_ok": bool(raw & (1 << 0)),
            "conversion_ready": bool(raw & (1 << 1)),
            "power_over_limit": bool(raw & (1 << 2)),
            "bus_under_limit": bool(raw & (1 << 3)),
            "bus_over_limit": bool(raw & (1 << 4)),
            "shunt_under_limit": bool(raw & (1 << 5)),
            "shunt_over_limit": bool(raw & (1 << 6)),
            "temperature_over_limit": bool(raw & (1 << 7)),
            "math_overflow": bool(raw & (1 << 9)),
        }

    def has_fault(self) -> bool:
        diagnostics = self.read_diagnostics()
        fault_keys = (
            "power_over_limit",
            "bus_under_limit",
            "bus_over_limit",
            "shunt_under_limit",
            "shunt_over_limit",
            "temperature_over_limit",
            "math_overflow",
        )
        return (not bool(diagnostics["memory_ok"])) or any(
            bool(diagnostics[key]) for key in fault_keys
        )

    def read_u16(self, register: int) -> int:
        return int.from_bytes(self._read(register, 2), "big")

    def read_u24(self, register: int) -> int:
        return int.from_bytes(self._read(register, 3), "big")

    def write_u16(self, register: int, value: int) -> None:
        self._require_connected()
        if not 0 <= value <= 0xFFFF:
            raise ValueError("INA229 16-bit register value is out of range")
        assert self._spi is not None
        command = (register & 0x3F) << 2
        self._spi.xfer2([command, (value >> 8) & 0xFF, value & 0xFF])

    def _read(self, register: int, length: int) -> bytes:
        self._require_connected()
        assert self._spi is not None
        command = ((register & 0x3F) << 2) | 0x01
        response = self._spi.xfer2([command] + [0] * length)
        if len(response) != length + 1:
            raise RuntimeError(
                f"INA229 SPI returned {len(response)} bytes, expected {length + 1}"
            )
        return bytes(response[1:])

    def _calibration_value(self) -> int:
        multiplier = 4 if self.adc_range == 1 else 1
        raw = round(
            13_107_200_000 * self.current_lsb_a * self.shunt_ohms * multiplier
        )
        if not 0 < raw <= 0x7FFF:
            raise ValueError("INA229 SHUNT_CAL value is outside the 15-bit range")
        return raw

    def _require_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("INA229 SPI device is not connected")

    @staticmethod
    def _signed(value: int, bits: int) -> int:
        sign_bit = 1 << (bits - 1)
        return value - (1 << bits) if value & sign_bit else value


class MockINA229:
    """Stateful INA229 substitute for dry runs and backend unit tests."""

    def __init__(self, *, voltage_v: float = 5.0, current_a: float = 0.0) -> None:
        self.voltage_v = voltage_v
        self.current_a = current_a
        self.current_limit_a = 3.0
        self.is_connected = False
        self.fault = False
        self.output_enabled = False

    def connect(self) -> None:
        self.is_connected = True

    def close(self) -> None:
        self.is_connected = False

    def identify(self) -> str:
        return "MOCK TI INA229 rev.1"

    def configure(self, *, current_limit_a: float | None = None) -> None:
        if current_limit_a is not None:
            self.current_limit_a = current_limit_a

    def set_overcurrent_limit(self, current_limit_a: float) -> int:
        self.current_limit_a = current_limit_a
        return round(current_limit_a * 0.01 / 5e-6)

    def read_bus_voltage(self) -> float:
        return self.voltage_v if self.output_enabled else 0.0

    def read_current(self) -> float:
        return self.current_a if self.output_enabled else 0.0

    def set_output_enabled(self, enabled: bool) -> None:
        self.output_enabled = enabled

    def read_diagnostics(self) -> dict[str, bool | int]:
        return {
            "raw": (1 << 6) | 1 if self.fault else 1,
            "memory_ok": True,
            "shunt_over_limit": self.fault,
        }

    def has_fault(self) -> bool:
        return self.fault
