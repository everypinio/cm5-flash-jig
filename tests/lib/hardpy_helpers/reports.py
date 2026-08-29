import hardpy
import pytest

from tests.lib.hardpy_helpers.utils import _hardpy_enabled


def set_measurement(request: pytest.FixtureRequest, name: str, value: str) -> None:
    if not _hardpy_enabled(request):
        return
    hardpy.set_case_measurement(hardpy.StringMeasurement(name=name, value=value))


def set_numeric_measurement(
    request: pytest.FixtureRequest,
    name: str,
    value: float,
    unit: str | None = None,
) -> None:
    if not _hardpy_enabled(request):
        return
    hardpy.set_case_measurement(
        hardpy.NumericMeasurement(name=name, value=value, unit=unit)
    )
