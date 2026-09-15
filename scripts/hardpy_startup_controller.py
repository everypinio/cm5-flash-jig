from __future__ import annotations

import base64
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

POWER_ON_DIR = ROOT_DIR / "testplans" / "power_on"
PYTHON = ROOT_DIR / ".venv" / "bin" / "python"
HARDPY = ROOT_DIR / ".venv" / "bin" / "hardpy"
PANEL_URL = "http://127.0.0.1:8000"
COUCHDB_UP_URL = "http://127.0.0.1:5984/_up"
MAIN_STATESTORE_URL = "http://127.0.0.1:5984/statestore/0.0.0.0_8000"
POLL_INTERVAL_S = 1
STARTUP_TIMEOUT_S = 30
DATABASE_TIMEOUT_S = 90
COLLECTION_TIMEOUT_S = 60
DISPLAY_HISTORY_LINES = 8
DUT_POLL_INTERVAL_S = 0.25
DUT_DEBOUNCE_S = 0.5
READY_HEARTBEAT_S = 1.0
WAIT_LOG_INTERVAL_S = 30.0


class PresenceMonitor(Protocol):
    def is_dut_present(self) -> bool: ...


class StartupDisplay:
    """Best-effort startup status output for the operator display."""

    def __init__(self) -> None:
        self._driver: Any | None = None
        self._panel: Any | None = None
        self._history: list[str] = []

    def open(
        self,
        *,
        show_logo: bool = False,
        show_terminal: bool = True,
    ) -> None:
        if self._panel is not None:
            return
        try:
            from tests.lib.drivers.display.dfr0997_operator_panel import (
                DFR0997Display,
                DFR0997OperatorPanel,
            )

            self._driver = DFR0997Display()
            self._panel = DFR0997OperatorPanel(display=self._driver)
            if show_logo:
                self._panel.show_everypin_logo()
            if show_terminal:
                self._panel.terminal_start("CM5 startup")
                for line in self._history:
                    self._panel.terminal_log(line)
        except Exception as exc:  # noqa: BLE001
            self.close()
            print(f"Startup display is unavailable: {exc}", file=sys.stderr, flush=True)

    def log(self, message: str) -> None:
        print(f"Startup: {message}", flush=True)
        self._history.append(message)
        self._history = self._history[-DISPLAY_HISTORY_LINES:]
        if self._panel is None:
            return
        try:
            self._panel.terminal_log(message)
        except Exception as exc:  # noqa: BLE001
            print(f"Startup display update failed: {exc}", file=sys.stderr, flush=True)
            self.close()

    def show_ready(self, elapsed_s: float = 0) -> None:
        self.open(show_terminal=False)
        if self._panel is None:
            return
        try:
            self._panel.show_waiting_for_dut(elapsed_s)
        except Exception as exc:  # noqa: BLE001
            print(f"Ready display failed: {exc}", file=sys.stderr, flush=True)
            self.close()

    def update_ready(self, elapsed_s: float) -> None:
        if self._panel is None:
            return
        try:
            self._panel.update_waiting_for_dut(elapsed_s)
        except Exception as exc:  # noqa: BLE001
            print(f"Ready display update failed: {exc}", file=sys.stderr, flush=True)
            self.close()

    def close(self) -> None:
        driver = self._driver
        self._driver = None
        self._panel = None
        if driver is None:
            return
        try:
            driver.close()
        except Exception as exc:  # noqa: BLE001
            print(f"Startup display close failed: {exc}", file=sys.stderr, flush=True)


def request_json(path: str) -> dict:
    request = Request(f"{PANEL_URL}{path}")
    with urlopen(request, timeout=5) as response:
        return json.load(response)


def wait_for_database() -> None:
    deadline = time.monotonic() + DATABASE_TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            with urlopen(COUCHDB_UP_URL, timeout=5) as response:
                if json.load(response).get("status") == "ok":
                    return
        except (OSError, URLError, json.JSONDecodeError):
            pass
        time.sleep(POLL_INTERVAL_S)
    raise RuntimeError("CouchDB did not become ready")


def wait_for_panel() -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            if request_json("/api/status").get("status") == "ready":
                return
        except (OSError, URLError):
            pass
        time.sleep(POLL_INTERVAL_S)
    raise RuntimeError("HardPy panel did not become ready")


def get_main_report() -> dict:
    request = Request(MAIN_STATESTORE_URL)
    credentials = base64.b64encode(b"dev:dev").decode("ascii")
    request.add_header("Authorization", f"Basic {credentials}")
    try:
        with urlopen(request, timeout=5) as response:
            return json.load(response)
    except HTTPError as exc:
        if exc.code == 404:
            return {}
        raise


def get_power_on_report() -> dict:
    document_id = request_json("/api/database_document_id").get("document_id")
    response = request_json("/api/json_data")
    if error := response.get("error"):
        raise RuntimeError(f"Could not read power-on JSON storage: {error}")
    for row in response.get("rows", []):
        if row.get("id") == document_id:
            return row.get("doc", {})
    return {}


def wait_for_collection(report_reader: Callable[[], dict]) -> None:
    deadline = time.monotonic() + COLLECTION_TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            report = report_reader()
            if (
                report.get("status") == "ready"
                and report.get("modules")
                and not report.get("start_time")
            ):
                return
        except (OSError, URLError, RuntimeError, json.JSONDecodeError):
            pass
        time.sleep(POLL_INTERVAL_S)
    raise RuntimeError("HardPy test collection did not become ready")


def report_passed(report: dict, previous_start_time: int) -> bool:
    start_time = report.get("start_time") or 0
    if start_time <= previous_start_time:
        return False
    modules = report.get("modules", {}).values()
    return (
        report.get("status") == "passed"
        and bool(modules)
        and all(module.get("status") == "passed" for module in modules)
    )


def report_finished(report: dict, previous_start_time: int) -> bool:
    start_time = report.get("start_time") or 0
    if start_time <= previous_start_time:
        return False
    return report.get("status") in {"passed", "failed", "skipped", "stopped"}


def _wait_for_dut_state(
    monitor: PresenceMonitor,
    *,
    present: bool,
    on_tick: Callable[[float], None] | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> float:
    started_at = clock()
    stable_since: float | None = None
    last_heartbeat_s = -1
    next_log_at_s = WAIT_LOG_INTERVAL_S
    state_name = "installation" if present else "removal"

    while True:
        now = clock()
        if monitor.is_dut_present() is present:
            if stable_since is None:
                stable_since = now
            elif now - stable_since >= DUT_DEBOUNCE_S:
                elapsed_s = now - started_at
                print(f"DUT {state_name} detected after {elapsed_s:.1f} s", flush=True)
                return elapsed_s
        else:
            stable_since = None

        elapsed_s = now - started_at
        heartbeat_s = int(elapsed_s // READY_HEARTBEAT_S)
        if on_tick is not None and heartbeat_s > last_heartbeat_s:
            on_tick(elapsed_s)
            last_heartbeat_s = heartbeat_s
        if elapsed_s >= next_log_at_s:
            print(f"Waiting for DUT {state_name}: {elapsed_s:.0f} s", flush=True)
            next_log_at_s += WAIT_LOG_INTERVAL_S
        sleep(DUT_POLL_INTERVAL_S)


def wait_for_lid_closed(
    monitor: PresenceMonitor,
    startup_display: StartupDisplay,
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    print("Ready: waiting for the lid to close", flush=True)
    startup_display.show_ready(0)
    _wait_for_dut_state(
        monitor,
        present=True,
        on_tick=startup_display.update_ready,
        clock=clock,
        sleep=sleep,
    )


def wait_for_lid_open(
    monitor: PresenceMonitor,
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    print("Test finished: waiting for the lid to open", flush=True)
    _wait_for_dut_state(
        monitor,
        present=False,
        clock=clock,
        sleep=sleep,
    )


def wait_for_main_test(
    panel: subprocess.Popen[bytes],
    monitor: PresenceMonitor,
    previous_start_time: int,
    *,
    report_reader: Callable[[], dict] = get_main_report,
    api_request: Callable[[str], dict] = request_json,
    panel_ready_waiter: Callable[[], None] = wait_for_panel,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    lid_open_since: float | None = None
    stop_requested = False
    next_report_at = 0.0

    while True:
        if panel.poll() is not None:
            raise RuntimeError(f"Main HardPy panel exited with code {panel.returncode}")

        now = clock()
        if monitor.is_dut_present():
            lid_open_since = None
        elif lid_open_since is None:
            lid_open_since = now
        elif not stop_requested and now - lid_open_since >= DUT_DEBOUNCE_S:
            response = api_request("/api/stop")
            if response.get("status") not in {"stopped", "ready"}:
                raise RuntimeError(f"HardPy did not accept stop request: {response}")
            print("Lid opened during test: HardPy stop requested", flush=True)
            stop_requested = True

        if stop_requested:
            status = api_request("/api/status").get("status")
            if status == "ready":
                try:
                    report = report_reader()
                except (OSError, URLError, RuntimeError, json.JSONDecodeError):
                    report = {}
                panel_ready_waiter()
                if report_finished(report, previous_start_time):
                    return report
                return {"status": "stopped", "start_time": previous_start_time + 1}

        if now >= next_report_at:
            next_report_at = now + POLL_INTERVAL_S
            try:
                report = report_reader()
            except (OSError, URLError, RuntimeError, json.JSONDecodeError) as exc:
                print(
                    f"Transient error while reading main report: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
            else:
                if report_finished(report, previous_start_time):
                    panel_ready_waiter()
                    return report

        sleep(DUT_POLL_INTERVAL_S)


def terminate_panel(panel: subprocess.Popen[bytes]) -> None:
    if panel.poll() is not None:
        return
    try:
        os.killpg(panel.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        panel.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(panel.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        panel.wait()


def run_main_panel(startup_display: StartupDisplay) -> None:
    from tests.lib.drivers.jig_gpio import DutPresenceMonitor

    startup_display.log("Starting main panel")
    panel = subprocess.Popen(
        [str(HARDPY), "run", str(ROOT_DIR)],
        cwd=ROOT_DIR,
        env=os.environ.copy(),
        start_new_session=True,
    )
    try:
        startup_display.log("Waiting for main panel")
        wait_for_panel()
        startup_display.log("Collecting main tests")
        wait_for_collection(get_main_report)

        with DutPresenceMonitor() as monitor:
            while True:
                wait_for_lid_closed(monitor, startup_display)
                previous_start_time = get_main_report().get("start_time", 0) or 0
                startup_display.close()

                response = request_json("/api/start")
                if response.get("status") != "started":
                    raise RuntimeError(f"HardPy did not start tests: {response}")
                print("Lid closed: main HardPy test started", flush=True)

                report = wait_for_main_test(panel, monitor, previous_start_time)
                print(
                    f"Main HardPy test finished with status: {report.get('status')}",
                    flush=True,
                )
                monitor.restore_input()
                wait_for_lid_open(monitor)
    except BaseException:
        terminate_panel(panel)
        raise


def main() -> int:
    startup_display = StartupDisplay()
    startup_display.open()
    panel: subprocess.Popen[bytes] | None = None
    stage = "Starting power-on panel"
    startup_display.log(stage)
    try:
        panel = subprocess.Popen(
            [str(HARDPY), "run", str(POWER_ON_DIR)],
            cwd=POWER_ON_DIR,
            env=os.environ.copy(),
            start_new_session=True,
        )
        stage = "Waiting for power-on panel"
        startup_display.log(stage)
        wait_for_panel()
        stage = "Collecting power-on tests"
        startup_display.log(stage)
        wait_for_collection(get_power_on_report)
        previous_start_time = get_power_on_report().get("start_time", 0) or 0
        stage = "Starting power-on tests"
        startup_display.log(stage)
        startup_display.close()
        request_json("/api/start")

        while True:
            stage = "Reading power-on report"
            time.sleep(POLL_INTERVAL_S)
            try:
                report = get_power_on_report()
            except (OSError, URLError, RuntimeError, json.JSONDecodeError) as exc:
                print(f"Transient error while reading power-on report: {exc}", file=sys.stderr)
                continue
            if not report_finished(report, previous_start_time):
                continue
            if report_passed(report, previous_start_time):
                startup_display.open()
                startup_display.log("Power-on tests passed")
                stage = "Waiting for CouchDB"
                startup_display.log(stage)
                wait_for_database()
                startup_display.log("CouchDB is ready")
                stage = "Stopping power-on panel"
                startup_display.log(stage)
                terminate_panel(panel)
                stage = "Starting main HardPy panel"
                run_main_panel(startup_display)
            print("Power-on HardPy test failed; keeping the power-on test plan active.")
            panel.wait()
            return panel.returncode or 1
    except (
        OSError,
        URLError,
        RuntimeError,
        subprocess.SubprocessError,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        error_message = f"Startup HardPy controller failed during {stage}: {exc}"
        print(error_message, file=sys.stderr, flush=True)
        if panel is not None:
            terminate_panel(panel)
        startup_display.open()
        startup_display.log(f"ERROR: {stage}")
        startup_display.close()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
