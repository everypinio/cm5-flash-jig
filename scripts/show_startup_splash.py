#!/usr/bin/env python3
"""Show the operator splash screen as early as possible during host boot."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

ROOT_DIR = Path(__file__).resolve().parents[1]
SPLASH_IMAGE = ROOT_DIR / "tests" / "assets" / "everypin_logo.png"


class SplashDisplay(Protocol):
    def clear(self, delay_s: float = 1.5) -> None: ...

    def background_image(self, filename: str | Path, *, location: int = 1) -> None: ...

    def close(self) -> None: ...


def create_display() -> SplashDisplay:
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))

    from tests.lib.drivers.display.dfr0997_display import DFR0997I2CDisplay

    return DFR0997I2CDisplay()


def show_startup_splash(
    image_path: Path = SPLASH_IMAGE,
    *,
    attempts: int = 30,
    retry_delay_s: float = 0.1,
    display_factory: Callable[[], SplashDisplay] = create_display,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Show the splash, retrying briefly while the early-boot I2C bus settles."""

    if not image_path.is_file():
        raise FileNotFoundError(f"Startup splash image was not found: {image_path}")
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    last_error: OSError | None = None
    for attempt in range(1, attempts + 1):
        try:
            display = display_factory()
            try:
                display.clear(delay_s=0.2)
                display.background_image(image_path)
            finally:
                display.close()
            print(f"Startup splash displayed on attempt {attempt}", flush=True)
            return
        except OSError as exc:
            last_error = exc
            if attempt < attempts:
                sleep(retry_delay_s)

    raise RuntimeError(
        f"Could not display startup splash after {attempts} attempts"
    ) from last_error


def main() -> int:
    try:
        show_startup_splash()
    except Exception as exc:  # noqa: BLE001
        print(f"Startup splash failed: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
