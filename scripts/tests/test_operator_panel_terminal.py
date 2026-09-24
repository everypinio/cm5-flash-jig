from __future__ import annotations

import unittest
from unittest.mock import Mock, call

from tests.lib.drivers.display.dfr0997_operator_panel import DFR0997OperatorPanel


class OperatorPanelTerminalTests(unittest.TestCase):
    def test_ready_preserves_previous_result_and_color_while_timer_updates(self) -> None:
        for status, label, color in (
            ("passed", "PASS", 0x78AD5C),
            ("failed", "FAIL", 0xFF6669),
            ("stopped", "STOP", 0xF2B24C),
        ):
            with self.subTest(status=status):
                display = Mock()
                panel = DFR0997OperatorPanel(display=display)
                panel.show_waiting_for_dut(0, last_run_status=status)
                display.reset_mock()
                panel.update_waiting_for_dut(3661)
                self.assertEqual(
                    display.text.call_args_list,
                    [
                        call(46, 216, "LAST:", size=1, color=0x1565C0, obj_id=91),
                        call(118, 216, label, size=1, color=color, obj_id=92),
                        call(198, 216, "01:01:01", size=1, color=0x1565C0, obj_id=93),
                    ],
                )
                display.background_image.assert_not_called()

    def test_ready_without_previous_run_keeps_wait_and_timer(self) -> None:
        display = Mock()
        panel = DFR0997OperatorPanel(display=display)
        panel.show_waiting_for_dut(0)
        display.text.assert_called_once_with(
            78, 216, "WAIT 00:00:00 |", size=1, color=0x1565C0, obj_id=91
        )

    def test_wrapped_message_uses_two_rows_before_next_message(self) -> None:
        display = Mock()
        panel = DFR0997OperatorPanel(display=display)
        panel.terminal_start()
        display.reset_mock()

        panel.terminal_log("Switching PowerBlock off")
        panel.terminal_log("Next")

        self.assertEqual(
            display.text.call_args_list,
            [
                call(8, 58, "> Switching PowerBlock", size=1, color=0, obj_id=10),
                call(8, 80, "  off", size=1, color=0, obj_id=11),
                call(8, 102, "> Next", size=1, color=0, obj_id=12),
            ],
        )

    def test_scrolling_updates_rows_without_clearing_screen(self) -> None:
        display = Mock()
        panel = DFR0997OperatorPanel(display=display)
        panel.terminal_start()
        for index in range(panel.terminal_max_lines):
            panel.terminal_log(f"Line {index}")
        display.reset_mock()

        panel.terminal_log("Line 8")

        display.clear.assert_not_called()
        display.background.assert_not_called()
        self.assertEqual(
            display.text.call_args_list,
            [
                call(
                    8,
                    58 + index * 22,
                    f"> Line {index + 1}",
                    size=1,
                    color=0,
                    obj_id=10 + index,
                )
                for index in range(panel.terminal_max_lines)
            ],
        )


if __name__ == "__main__":
    unittest.main()
