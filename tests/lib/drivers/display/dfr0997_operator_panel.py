from dataclasses import field
from pathlib import Path
import textwrap
import time

from hardpy.pytest_hardpy.pytest_call import dataclass, sleep

from tests import ASSETS_DATA_PATH
from tests.env import settings
from tests.lib.drivers.display.dfr0997_display import DFR0997I2CDisplay
from tests.lib.drivers.display.dfr0997_display_interface import (
    BLACK,
    BLUE,
    WHITE,
    DFR0997DisplayInterface,
)
from tests.lib.drivers.display.dfr0997_display_mock import DFR0997MockDisplay

DFR0997Display = DFR0997I2CDisplay if not settings.MOCK_DISPLAY else DFR0997MockDisplay


@dataclass
class DFR0997OperatorPanel:
    """High-level representation of information panels for the operator."""

    display: DFR0997DisplayInterface
    terminal_max_lines: int = 8
    terminal_max_chars: int = 24
    terminal_lines: list[str] = field(default_factory=list)
    terminal_title: str = "CM5 Flash JIG"
    logo_filename: Path = ASSETS_DATA_PATH / "everypin_logo.png"
    ready_filename: Path = ASSETS_DATA_PATH / "everypin_ready.png"
    remove_dut_filename: Path = ASSETS_DATA_PATH / "everypin_remove_dut.png"
    pass_filename: Path = ASSETS_DATA_PATH / "everypin_pass.png"
    fail_filename: Path = ASSETS_DATA_PATH / "everypin_fail.png"
    terminal_visible: bool = False
    terminal_rendered_lines: int = 0

    def _leave_terminal(self) -> None:
        self.terminal_visible = False
        self.terminal_rendered_lines = 0

    def _show_background_image(self, filename: str | Path) -> None:
        self.display.clear(delay_s=0.2)
        self.display.background_image(filename)
        self._leave_terminal()

    def _fit_text(self, value: str, max_chars: int = 29) -> str:
        text = value.encode("ascii", errors="replace").decode("ascii")
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 1] + "."

    def _fit_lines(
        self, value: str, *, max_chars: int = 24, max_lines: int = 2
    ) -> list[str]:
        words = value.encode("ascii", errors="replace").decode("ascii").split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = word[:max_chars]
            if len(lines) == max_lines:
                break
        if current and len(lines) < max_lines:
            lines.append(current)
        if not lines:
            lines.append("")
        if len(lines) == max_lines and len(" ".join(words)) > sum(
            len(line) for line in lines
        ):
            lines[-1] = self._fit_text(lines[-1], max_chars)
        return lines[:max_lines]

    def show_everypin_logo(self, delay_s: float = 1.2) -> None:
        self._show_background_image(self.logo_filename)
        time.sleep(delay_s)

    def terminal_start(self, title: str = "CM5 Flash JIG") -> None:
        self.terminal_title = title
        self.terminal_lines.clear()
        self._render_terminal()

    def terminal_log(self, message: str) -> None:
        previous_line_count = len(self.terminal_lines)
        message_lines = self._wrap_terminal_message(message)
        self.terminal_lines.extend(message_lines)
        if len(self.terminal_lines) > self.terminal_max_lines:
            self.terminal_lines = self.terminal_lines[-self.terminal_max_lines :]
            if self.terminal_visible:
                self._update_terminal_rows()
            else:
                self._render_terminal()
            return

        if (
            self.terminal_visible
            and self.terminal_rendered_lines == previous_line_count
        ):
            for offset, line in enumerate(message_lines):
                self._draw_terminal_line(previous_line_count + offset, line)
            self.terminal_rendered_lines = len(self.terminal_lines)
            return

        self._render_terminal()

    def _wrap_terminal_message(self, message: str) -> list[str]:
        text = message.encode("ascii", errors="replace").decode("ascii")
        content_width = max(1, self.terminal_max_chars - 2)
        rendered_lines: list[str] = []

        for source_line in text.splitlines() or [""]:
            wrapped_lines = textwrap.wrap(
                source_line,
                width=content_width,
                break_long_words=True,
                break_on_hyphens=False,
            ) or [""]
            for wrapped_line in wrapped_lines:
                prefix = "> " if not rendered_lines else "  "
                rendered_lines.append(f"{prefix}{wrapped_line}")

        return rendered_lines

    def terminal_restore(self) -> None:
        self._render_terminal()

    def _render_terminal(self) -> None:
        self.display.clear()
        self.display.background(WHITE)
        self.display.text(
            8, 10, self._fit_text(self.terminal_title, 22), size=1, color=BLUE, obj_id=1
        )
        self.display.text(8, 34, "-" * 24, size=1, color=BLACK, obj_id=2)
        for index, line in enumerate(self.terminal_lines):
            self._draw_terminal_line(index, line)
        self.terminal_visible = True
        self.terminal_rendered_lines = len(self.terminal_lines)

    def _update_terminal_rows(self) -> None:
        for index, line in enumerate(self.terminal_lines):
            self._draw_terminal_line(index, line)
        self.terminal_rendered_lines = len(self.terminal_lines)

    def _draw_terminal_line(self, index: int, line: str) -> None:
        y = 58 + index * 22
        self.display.text(
            8,
            y,
            self._fit_text(line, self.terminal_max_chars),
            size=1,
            color=BLACK,
            obj_id=10 + index,
        )

    def show_message(
        self,
        title: str,
        subtitle: str = "",
        *,
        foreground: int = BLACK,
        background: int = WHITE,
    ) -> None:
        self.display.clear()
        self.display.background(background)
        self._leave_terminal()
        self.display.text(20, 50, title, size=2, color=foreground, obj_id=1)
        if subtitle:
            self.display.text(20, 95, subtitle, size=1, color=foreground, obj_id=2)

    def show_logo(self) -> None:
        self.show_everypin_logo()

    def show_starting(self) -> None:
        self.terminal_start()
        self.terminal_log("Initializing JIG")

    def show_preparing_for_work(self) -> None:
        self.terminal_log("Preparing for work")

    def show_remove_compute_module(self) -> None:
        self._show_background_image(self.remove_dut_filename)

    def show_ready(self) -> None:
        self._show_background_image(self.ready_filename)

    def show_waiting_for_dut(self, elapsed_s: float = 0) -> None:
        self._show_background_image(self.ready_filename)
        self.update_waiting_for_dut(elapsed_s)

    def update_waiting_for_dut(self, elapsed_s: float) -> None:
        total_seconds = max(0, int(elapsed_s))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        spinner = "|/-\\"[total_seconds % 4]
        status = f"WAIT {hours:02d}:{minutes:02d}:{seconds:02d} {spinner}"
        self.display.draw_rect(
            58,
            210,
            204,
            27,
            fill_color=WHITE,
            obj_id=90,
        )
        self.display.text(78, 216, status, size=1, color=BLUE, obj_id=91)

    def show_flashing(self) -> None:
        self.terminal_log("FLASHING: writing image")

    def show_pass(self) -> None:
        self._show_background_image(self.pass_filename)

    def show_fail(self, reason: str = "Test failed") -> None:
        self._show_background_image(self.fail_filename)
        self.display.text(42, 142, "FAILED STEP", size=1, color=WHITE, obj_id=1)
        for index, line in enumerate(
            self._fit_lines(reason, max_chars=24, max_lines=2)
        ):
            self.display.text(
                42, 170 + index * 24, line, size=1, color=WHITE, obj_id=2 + index
            )


def run_smoke_test() -> None:
    with DFR0997Display() as display_driver:
        panel = DFR0997OperatorPanel(display=display_driver)
        sleep(2)
        screens = [
            panel.show_logo,
            panel.show_starting,
            panel.show_ready,
            panel.show_flashing,
            panel.show_pass,
            lambda: panel.show_fail("No boot"),
        ]
        for screen in screens:
            screen()
            sleep(2.0)
        panel.show_ready()


if __name__ == "__main__":
    run_smoke_test()
