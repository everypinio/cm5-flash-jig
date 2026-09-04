from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call

from scripts.show_shutdown_screen import show_shutdown_screen
from tests.lib.drivers.display.dfr0997_display_interface import BLACK


class FakeDisplay:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def clear(self, delay_s: float = 1.5) -> None:
        self.calls.append(call.clear(delay_s=delay_s))

    def background(self, color: int, delay_s: float = 0.3) -> None:
        self.calls.append(call.background(color, delay_s=delay_s))

    def background_image(
        self, filename: str | Path, *, location: int = 1
    ) -> None:
        self.calls.append(call.background_image(filename, location=location))

    def close(self) -> None:
        self.calls.append(call.close())


class ShutdownScreenTests(unittest.TestCase):
    def test_screen_is_cleared_blacked_out_and_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            image_path = Path(temporary_directory) / "everypin_shutdown.png"
            image_path.touch()
            display = FakeDisplay()

            show_shutdown_screen(
                image_path,
                display_factory=lambda: display,
            )

        self.assertEqual(
            display.calls,
            [
                call.clear(delay_s=0.0),
                call.background(BLACK, delay_s=0.0),
                call.background_image(image_path, location=1),
                call.close(),
            ],
        )

    def test_i2c_open_is_retried(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            image_path = Path(temporary_directory) / "everypin_shutdown.png"
            image_path.touch()
            display = FakeDisplay()
            factory = Mock(side_effect=[OSError("I2C not ready"), display])
            sleep = Mock()

            show_shutdown_screen(
                image_path,
                attempts=2,
                retry_delay_s=0.1,
                display_factory=factory,
                sleep=sleep,
            )

        self.assertEqual(factory.call_count, 2)
        sleep.assert_called_once_with(0.1)
        self.assertEqual(display.calls[-1], call.close())

    def test_missing_image_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_path = Path(temporary_directory) / "missing.png"

            with self.assertRaises(FileNotFoundError):
                show_shutdown_screen(missing_path)


if __name__ == "__main__":
    unittest.main()
