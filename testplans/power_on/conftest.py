import hardpy
import pytest

from testplans.power_on.metadata import set_power_on_hardpy_metadata
from tests.env import settings

pytest_plugins = ("tests.conftest",)

@pytest.fixture(scope="session", autouse=True)
def set_hardpy_testplan_metadata(
	request: pytest.FixtureRequest,
) -> None:
	if not getattr(request.config.option, "hardpy_pt", False):
		return
	if request.config.option.collectonly:
		return

	set_power_on_hardpy_metadata(hardpy, settings)

HARDPY_USER_NAME = "User"
HARDPY_DUT_NAME = "CM5 flasher"
HARDPY_DUT_TYPE = "test jig"
HARDPY_STAND_NAME = "CM5 flasher"
