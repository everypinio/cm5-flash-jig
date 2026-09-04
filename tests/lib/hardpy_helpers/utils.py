import pytest


def _hardpy_enabled(request: pytest.FixtureRequest) -> bool:
    return bool(getattr(request.config.option, "hardpy_pt", False))
