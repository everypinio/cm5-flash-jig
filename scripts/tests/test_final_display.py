from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from hardpy.pytest_hardpy.utils.const import TestStatus

from tests import conftest
from tests.lib.drivers.display.dfr0997_operator_panel import DFR0997OperatorPanel


class FinalDisplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.report_reader = self.enterContext(
            patch.object(conftest.hardpy, "get_current_report")
        )
        self.driver = self.enterContext(patch.object(conftest, "DFR0997Display"))
        self.panel = self.enterContext(
            patch.object(conftest, "DFR0997OperatorPanel")
        ).return_value
        self.enterContext(patch.object(conftest, "failed_display_step", None))

    def test_stopped_report_shows_only_stop_even_with_previous_failure(self) -> None:
        for failed_step in (None, "2.3. Flash image"):
            with self.subTest(failed_step=failed_step):
                self.panel.reset_mock()
                conftest.failed_display_step = failed_step
                self.report_reader.return_value = SimpleNamespace(status=TestStatus.STOPPED)
                conftest.finish_executing()
                self.panel.show_stop.assert_called_once_with()
                self.panel.show_pass.assert_not_called()
                self.panel.show_fail.assert_not_called()

    def test_pass_requires_passed_report(self) -> None:
        self.report_reader.return_value = SimpleNamespace(status=TestStatus.PASSED)
        conftest.finish_executing()
        self.panel.show_pass.assert_called_once_with()
        self.panel.show_stop.assert_not_called()

    def test_failed_report_retains_failed_step(self) -> None:
        conftest.failed_display_step = "2.3. Flash image"
        self.report_reader.return_value = SimpleNamespace(status=TestStatus.FAILED)
        conftest.finish_executing()
        self.panel.show_fail.assert_called_once_with("2.3. Flash image")
        self.panel.show_pass.assert_not_called()

    def test_missing_or_unfinished_report_never_shows_pass_or_stop(self) -> None:
        for status in (None, TestStatus.RUN, TestStatus.READY, TestStatus.SKIPPED, TestStatus.ERROR):
            with self.subTest(status=status):
                self.panel.reset_mock()
                self.report_reader.return_value = (
                    SimpleNamespace(status=status) if status is not None else None
                )
                conftest.finish_executing()
                self.panel.show_pass.assert_not_called()
                self.panel.show_stop.assert_not_called()
                self.panel.show_message.assert_called_once()

    def test_report_read_failure_does_not_escape_callback(self) -> None:
        self.report_reader.side_effect = RuntimeError("Database unavailable")
        conftest.finish_executing()
        self.panel.show_message.assert_called_once_with("UNKNOWN", "See HardPy report")
        self.panel.show_pass.assert_not_called()

    def test_display_failure_does_not_block_subsequent_upload(self) -> None:
        self.report_reader.return_value = SimpleNamespace(status=TestStatus.STOPPED)
        self.driver.side_effect = OSError("I2C unavailable")
        conftest.finish_executing()

    def test_stop_screen_uses_uploaded_asset_name_and_leaves_terminal(self) -> None:
        display = Mock()
        panel = DFR0997OperatorPanel(display=display)
        panel.terminal_start()
        display.reset_mock()
        panel.show_stop()
        self.assertEqual(panel.stop_filename.name, "everypin_stop.png")
        self.assertTrue(panel.stop_filename.is_file())
        display.background_image.assert_called_once_with(panel.stop_filename)
        self.assertFalse(panel.terminal_visible)


if __name__ == "__main__":
    unittest.main()
