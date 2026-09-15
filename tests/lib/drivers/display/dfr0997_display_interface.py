from abc import ABC, abstractmethod
from pathlib import Path
from typing import Self

BLACK = 0x000000
WHITE = 0xFFFFFF
RED = 0xFF0000
GREEN = 0x00C853
BLUE = 0x1565C0
YELLOW = 0xFFD600
EVERYPIN_PINK = 0xD34FEA


def rgb24(color: int) -> list[int]:
    return [(color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF]


def u16(value: int) -> list[int]:
    return [(value >> 8) & 0xFF, value & 0xFF]


class DFR0997DisplayInterface(ABC):
    """Abstract base class for DFR0997 display drivers."""

    @abstractmethod
    def clear(self, delay_s: float = 1.5) -> None:
        pass

    @abstractmethod
    def background(self, color: int, delay_s: float = 0.3) -> None:
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def draw_pixel(self, x: int, y: int, color: int, *, obj_id: int = 1) -> None:
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def draw_icon_external(
        self,
        x: int,
        y: int,
        filename: str | Path,
        *,
        zoom: int = 256,
        obj_id: int = 1,
    ) -> None:
        pass

    @abstractmethod
    def background_image(self, filename: str | Path, *, location: int = 1) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
