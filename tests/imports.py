import importlib
from types import ModuleType
from warnings import deprecated

import pytest

from tests.lib.hardpy_helpers.messages import fail_with_operator_message
from tests.lib.hardpy_helpers.utils import _hardpy_enabled


def _load_driver(
    request: pytest.FixtureRequest, module_path: str, failure_handler
) -> ModuleType | None:
    """
    Loads a driver module conditionally based on HardPy availability and handles failures.

    Args:
        request: The pytest FixtureRequest object.
        module_path: The full path to the driver module (e.g., "tests.lib.drivers.power_block_driver").
        failure_handler: A callable that takes (request, exception) and handles failure reporting.

    Returns:
        The imported module or None if import is skipped/failed.
    """
    if not _hardpy_enabled(request):
        return pytest.importorskip(module_path)

    try:
        return importlib.import_module(module_path)
    except Exception as exc:
        failure_handler(request, module_path, exc)


def load_power_module(request: pytest.FixtureRequest) -> ModuleType | None:
    """Loads the PowerBlock driver."""

    def handle_fail(req, mod, exc):
        fail_with_operator_message(req, f"PowerBlock driver is unavailable: {exc}")

    return _load_driver(request, "tests.lib.drivers.power_block", handle_fail)


def load_ads_module(request: pytest.FixtureRequest) -> ModuleType | None:
    """Loads the ADS1x15 driver."""

    def handle_fail(req, mod, exc):
        fail_with_operator_message(
            req, f"ADS1x15 driver is unavailable: {exc}", "Power lines"
        )

    return _load_driver(request, "tests.lib.drivers.ads1x15_driver", handle_fail)


@deprecated("Use direct module import for DFR0997 display")
def load_display_module(request: pytest.FixtureRequest) -> ModuleType | None:
    """Loads the DFR0997 display driver."""

    def handle_fail(req, mod, exc):
        pytest.fail(f"DFR0997 display init dependency is unavailable: {exc}")

    return _load_driver(request, "tests.lib.drivers.dfr0997_display", handle_fail)


def load_flasher_module(request: pytest.FixtureRequest) -> ModuleType | None:
    """Loads the CM5 USB flasher driver."""

    def handle_fail(req, mod, exc):
        fail_with_operator_message(
            req, f"USB flasher module is unavailable: {exc}", "USB boot"
        )

    return _load_driver(request, "tests.lib.drivers.flasher", handle_fail)
