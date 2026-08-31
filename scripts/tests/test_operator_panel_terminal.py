from __future__ import annotations

import unittest
from unittest.mock import Mock, call

from tests.lib.drivers.display.dfr0997_operator_panel import DFR0997OperatorPanel


class OperatorPanelTerminalTests(unittest.TestCase):
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
