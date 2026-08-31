from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call

from scripts.show_startup_splash import show_startup_splash


class FakeDisplay:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def clear(self, delay_s: float = 1.5) -> None:
        self.calls.append(call.clear(delay_s=delay_s))

    def background_image(
        self, filename: str | Path, *, location: int = 1
    ) -> None:
        self.calls.append(call.background_image(filename, location=location))

    def close(self) -> None:
        self.calls.append(call.close())


class StartupSplashTests(unittest.TestCase):
    def test_splash_is_cleared_drawn_and_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            image_path = Path(temporary_directory) / "everypin_logo.png"
            image_path.touch()
            display = FakeDisplay()

            show_startup_splash(
                image_path,
                display_factory=lambda: display,
            )

        self.assertEqual(
            display.calls,
            [
                call.clear(delay_s=0.2),
                call.background_image(image_path, location=1),
                call.close(),
            ],
        )

    def test_i2c_open_is_retried(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            image_path = Path(temporary_directory) / "everypin_logo.png"
            image_path.touch()
            display = FakeDisplay()
            factory = Mock(side_effect=[OSError("I2C not ready"), display])
            sleep = Mock()

            show_startup_splash(
                image_path,
                attempts=2,
                retry_delay_s=0.1,
                display_factory=factory,
                sleep=sleep,
            )

        self.assertEqual(factory.call_count, 2)
        sleep.assert_called_once_with(0.1)
        self.assertEqual(display.calls[-1], call.close())


if __name__ == "__main__":
    unittest.main()
