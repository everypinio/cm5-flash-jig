#!/usr/bin/env python3
"""Leave the operator display black while the CM5 shuts down."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

ROOT_DIR = Path(__file__).resolve().parents[1]
SHUTDOWN_IMAGE = ROOT_DIR / "tests" / "assets" / "everypin_shutdown.png"
BLACK = 0x000000


class ShutdownDisplay(Protocol):
    def clear(self, delay_s: float = 1.5) -> None: ...

    def background(self, color: int, delay_s: float = 0.3) -> None: ...

    def background_image(self, filename: str | Path, *, location: int = 1) -> None: ...

    def close(self) -> None: ...


def create_display() -> ShutdownDisplay:
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))

    from tests.lib.drivers.display.dfr0997_display import DFR0997I2CDisplay

    return DFR0997I2CDisplay()


def show_shutdown_screen(
    image_path: Path = SHUTDOWN_IMAGE,
    *,
    attempts: int = 2,
    retry_delay_s: float = 0.1,
    display_factory: Callable[[], ShutdownDisplay] = create_display,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Show the shutdown artwork, leaving a black fallback on the display."""

    if not image_path.is_file():
        raise FileNotFoundError(f"Shutdown image was not found: {image_path}")
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    last_error: OSError | None = None
    for attempt in range(1, attempts + 1):
        try:
            display = display_factory()
            try:
                # DFR0997 loads named bitmaps from its own storage. Set the
                # equivalent solid-black background first so shutdown remains
                # visually correct even if that storage is unavailable.
                display.clear(delay_s=0.0)
                display.background(BLACK, delay_s=0.0)
                display.background_image(image_path)
            finally:
                display.close()
            print(f"Shutdown screen displayed on attempt {attempt}", flush=True)
            return
        except OSError as exc:
            last_error = exc
            if attempt < attempts:
                sleep(retry_delay_s)

    raise RuntimeError(
        f"Could not display shutdown screen after {attempts} attempts"
    ) from last_error


def main() -> int:
    try:
        show_shutdown_screen()
    except Exception as exc:  # noqa: BLE001
        print(f"Shutdown screen failed: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
