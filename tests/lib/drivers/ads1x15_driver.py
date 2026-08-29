"""Minimal ADS1015/ADS1115 I2C voltage reader for the flash JIG."""

from __future__ import annotations

import time
from dataclasses import dataclass

from smbus2 import SMBus


ADS1X15_POINTER_CONVERSION = 0x00
ADS1X15_POINTER_CONFIG = 0x01

ADS1X15_MUX_SINGLE = {
    0: 0x4000,
    1: 0x5000,
    2: 0x6000,
    3: 0x7000,
}

ADS1X15_PGA = {
    6.144: 0x0000,
    4.096: 0x0200,
    2.048: 0x0400,
    1.024: 0x0600,
    0.512: 0x0800,
    0.256: 0x0A00,
}


@dataclass
class ADS1x15Reader:
    address: int = 0x48
    bus_id: int = 1
    full_scale_v: float = 4.096
    model: str = "ADS1015"
    conversion_delay_s: float | None = None

    def __post_init__(self) -> None:
        self.model = self.model.upper()
        if self.model not in {"ADS1015", "ADS1115"}:
            raise ValueError("ADC model must be ADS1015 or ADS1115")
        if self.full_scale_v not in ADS1X15_PGA:
            supported = ", ".join(str(value) for value in ADS1X15_PGA)
            raise ValueError(f"Unsupported ADS1x15 full scale: {self.full_scale_v}. Supported: {supported}")
        if self.conversion_delay_s is None:
            self.conversion_delay_s = 0.002 if self.model == "ADS1015" else 0.02
        self.bus = SMBus(self.bus_id)

    def __enter__(self) -> "ADS1x15Reader":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        if hasattr(self, 'bus') and self.bus is not None:
            self.bus.close()

    def read_voltage(self, channel: int, *, scale: float = 1.0) -> float:
        if channel not in ADS1X15_MUX_SINGLE:
            raise ValueError(f"ADS1x15 channel must be 0..3, got {channel}")

        config = (
            0x8000
            | ADS1X15_MUX_SINGLE[channel]
            | ADS1X15_PGA[self.full_scale_v]
            | 0x0100
            | 0x0080
            | 0x0003
        )
        self.bus.write_i2c_block_data(
            self.address,
            ADS1X15_POINTER_CONFIG,
            [(config >> 8) & 0xFF, config & 0xFF],
        )

        if (self.conversion_delay_s):
            time.sleep(self.conversion_delay_s)

        raw_bytes = self.bus.read_i2c_block_data(self.address, ADS1X15_POINTER_CONVERSION, 2)
        raw16 = (raw_bytes[0] << 8) | raw_bytes[1]
        if raw16 & 0x8000:
            raw16 -= 0x10000

        if self.model == "ADS1015":
            raw = raw16 >> 4
            divisor = 2048.0
        else:
            raw = raw16
            divisor = 32768.0

        return (raw * self.full_scale_v / divisor) * scale
