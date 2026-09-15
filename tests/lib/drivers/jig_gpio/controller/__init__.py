from tests.env import settings

from .mock import MockJigGPIOController
from .real import JigGPIOControllerImpl

JigGPIOController = (
    MockJigGPIOController if settings.MOCK_GPIO else JigGPIOControllerImpl
)


__all__ = ["JigGPIOController", "JigGPIOControllerImpl", "MockJigGPIOController"]
