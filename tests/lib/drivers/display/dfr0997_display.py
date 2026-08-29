"""Minimal DFRobot DFR0997 I2C display helper.

The module can be imported by the test stand software or run directly as a
small smoke test on Raspberry Pi.
"""

from __future__ import annotations

import errno
import time
from pathlib import Path
from typing import Iterable

from smbus2 import SMBus, i2c_msg

from tests.lib.drivers.display.dfr0997_display_interface import (
    BLACK,
    DFR0997DisplayInterface,
    rgb24,
    u16,
)

CMD_HEADER_HIGH = 0x55
CMD_HEADER_LOW = 0xAA
CMD_DRAW_PIXEL = 0x02
CMD_DRAW_RECT = 0x04
CMD_DRAW_ICON_EXTERNAL = 0x09
CMD_DRAW_TEXT = 0x18
CMD_BG_IMAGE = 0x1A
CMD_CLEAR = 0x1D
CMD_BG_COLOR = 0x19
MAX_EIO_RETRIES = 15
EIO_RETRY_DELAY_S = 0.1


class DFR0997I2CDisplay(DFR0997DisplayInterface):
    """Real I2C implementation for DFR0997 display."""

    def __init__(
        self,
        address: int = 0x2C,
        bus_id: int = 1,
        chunk_size: int = 32,
        chunk_delay_s: float = 0.02,
    ) -> None:
        self.address = address
        self.bus_id = bus_id
        self.chunk_size = chunk_size
        self.chunk_delay_s = chunk_delay_s
        self.bus = SMBus(self.bus_id)

    def close(self) -> None:
        if self.bus:
            self.bus.close()

    def send(self, command_bytes: Iterable[int]) -> None:
        data = list(command_bytes)
        for attempt in range(MAX_EIO_RETRIES):
            try:
                self.bus.i2c_rdwr(i2c_msg.write(self.address, data))
                break
            except OSError as exc:
                if exc.errno != errno.EIO or attempt == MAX_EIO_RETRIES - 1:
                    raise
                time.sleep(EIO_RETRY_DELAY_S)
        time.sleep(self.chunk_delay_s)

    def make_command(self, command: int, payload: list[int]) -> list[int]:
        length_after_header = len(payload) + 1
        return [CMD_HEADER_HIGH, CMD_HEADER_LOW, length_after_header, command] + payload

    def clear(self, delay_s: float = 1.5) -> None:
        self.send(self.make_command(CMD_CLEAR, []))
        time.sleep(delay_s)

    def background(self, color: int, delay_s: float = 0.3) -> None:
        self.send(self.make_command(CMD_BG_COLOR, rgb24(color)))
        time.sleep(delay_s)

    def text(
        self,
        x: int,
        y: int,
        value: str,
        *,
        size: int = 1,
        color: int = BLACK,
        obj_id: int = 1,
    ) -> None:
        data = value.encode("ascii")
        payload = [obj_id, size] + rgb24(color) + u16(x) + u16(y) + list(data)
        self.send(self.make_command(CMD_DRAW_TEXT, payload))

    def draw_pixel(self, x: int, y: int, color: int, *, obj_id: int = 1) -> None:
        payload = [obj_id] + rgb24(color) + u16(x) + u16(y)
        self.send(self.make_command(CMD_DRAW_PIXEL, payload))

    def draw_rect(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        *,
        fill_color: int,
        border_color: int | None = None,
        border_width: int = 0,
        rounded: int = 0,
        obj_id: int = 1,
    ) -> None:
        border = fill_color if border_color is None else border_color
        payload = (
            [obj_id, border_width]
            + rgb24(border)
            + [1]
            + rgb24(fill_color)
            + [rounded]
            + u16(x)
            + u16(y)
            + u16(width)
            + u16(height)
        )
        self.send(self.make_command(CMD_DRAW_RECT, payload))

    def draw_icon_external(
        self,
        x: int,
        y: int,
        filename: str | Path,
        *,
        zoom: int = 256,
        obj_id: int = 1,
    ) -> None:
        data = Path(filename).name.encode("ascii")
        payload = [obj_id] + u16(zoom) + u16(x) + u16(y) + list(data)
        self.send(self.make_command(CMD_DRAW_ICON_EXTERNAL, payload))

    def background_image(self, filename: str | Path, *, location: int = 1) -> None:
        data = Path(filename).name.encode("ascii")
        payload = [location] + list(data)
        self.send(self.make_command(CMD_BG_IMAGE, payload))
