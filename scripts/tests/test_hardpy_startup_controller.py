from __future__ import annotations

import unittest

from scripts import hardpy_startup_controller as controller


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, delay_s: float) -> None:
        self.now += delay_s


class TimedPresenceMonitor:
    def __init__(
        self,
        clock: FakeClock,
        *,
        switch_at_s: float,
        before: bool,
        after: bool,
    ) -> None:
        self.clock = clock
        self.switch_at_s = switch_at_s
        self.before = before
        self.after = after

    def is_dut_present(self) -> bool:
        if self.clock.now < self.switch_at_s:
            return self.before
        return self.after


class RecordingDisplay:
    def __init__(self) -> None:
        self.shown: list[float] = []
        self.updated: list[float] = []

    def show_ready(self, elapsed_s: float = 0) -> None:
        self.shown.append(elapsed_s)

    def update_ready(self, elapsed_s: float) -> None:
        self.updated.append(elapsed_s)


class RunningPanel:
    returncode = None

    def poll(self) -> None:
        return None


class StartupControllerTests(unittest.TestCase):
    def test_ready_waits_for_stable_lid_closure(self) -> None:
        clock = FakeClock()
        monitor = TimedPresenceMonitor(
            clock,
            switch_at_s=0.75,
            before=False,
            after=True,
        )
        display = RecordingDisplay()

        controller.wait_for_lid_closed(
            monitor,
            display,  # type: ignore[arg-type]
            clock=clock.monotonic,
            sleep=clock.sleep,
        )

        self.assertEqual(display.shown, [0])
        self.assertGreaterEqual(clock.now, 1.25)
        self.assertTrue(display.updated)

    def test_finished_test_keeps_result_until_lid_opens(self) -> None:
        clock = FakeClock()
        monitor = TimedPresenceMonitor(
            clock,
            switch_at_s=1.0,
            before=True,
            after=False,
        )

        controller.wait_for_lid_open(
            monitor,
            clock=clock.monotonic,
            sleep=clock.sleep,
        )

        self.assertGreaterEqual(clock.now, 1.5)

    def test_opening_lid_stops_running_hardpy_once(self) -> None:
        clock = FakeClock()
        monitor = TimedPresenceMonitor(
            clock,
            switch_at_s=0.5,
            before=True,
            after=False,
        )
        api_calls: list[str] = []
        ready_waits: list[bool] = []

        def api_request(path: str) -> dict:
            api_calls.append(path)
            if path == "/api/stop":
                return {"status": "stopped"}
            if path == "/api/status":
                return {"status": "ready"}
            raise AssertionError(path)

        report = controller.wait_for_main_test(
            RunningPanel(),  # type: ignore[arg-type]
            monitor,
            previous_start_time=10,
            report_reader=lambda: {"status": "run", "start_time": 11},
            api_request=api_request,
            panel_ready_waiter=lambda: ready_waits.append(True),
            clock=clock.monotonic,
            sleep=clock.sleep,
        )

        self.assertEqual(api_calls.count("/api/stop"), 1)
        self.assertEqual(api_calls.count("/api/status"), 1)
        self.assertEqual(report["status"], "stopped")
        self.assertEqual(ready_waits, [True])

    def test_closed_lid_allows_test_to_finish_normally(self) -> None:
        clock = FakeClock()
        monitor = TimedPresenceMonitor(
            clock,
            switch_at_s=100.0,
            before=True,
            after=True,
        )
        api_calls: list[str] = []
        ready_waits: list[bool] = []

        def report_reader() -> dict:
            status = "passed" if clock.now >= 1.0 else "run"
            return {"status": status, "start_time": 11}

        report = controller.wait_for_main_test(
            RunningPanel(),  # type: ignore[arg-type]
            monitor,
            previous_start_time=10,
            report_reader=report_reader,
            api_request=lambda path: api_calls.append(path) or {},
            panel_ready_waiter=lambda: ready_waits.append(True),
            clock=clock.monotonic,
            sleep=clock.sleep,
        )

        self.assertEqual(report["status"], "passed")
        self.assertEqual(api_calls, [])
        self.assertEqual(ready_waits, [True])


if __name__ == "__main__":
    unittest.main()
