from tests.env import settings

from tests.lib.drivers.power_block.interfaces import PowerBlockDriverInterface
from tests.lib.drivers.power_block.mock import MockPowerBlockDriver
from tests.lib.drivers.power_block.real import PowerBlockDriverImpl

if settings.MOCK_PWRBLOCK:
    PowerBlockDriver = MockPowerBlockDriver
else:
    PowerBlockDriver = PowerBlockDriverImpl

__all__ = ["PowerBlockDriver", "PowerBlockDriverInterface"]
