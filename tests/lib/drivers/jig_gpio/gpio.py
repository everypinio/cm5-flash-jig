from typing import Self

from tests.env import settings

from .backends import make_gpio_backend
from .constants import JIG_GPIO_CONFIG
from .interfaces import GPIOBackend


class JigGPIO:
    def __init__(self, backend: GPIOBackend | None = None) -> None:
        if settings.MOCK_GPIO:
            return

        self.backend = backend or make_gpio_backend()
        self._initialized = False

    def __enter__(self) -> Self:
        if settings.MOCK_GPIO:
            return self

        self.initialize()
        return self

    def __exit__(self, *exc_info: object) -> None:
        if settings.MOCK_GPIO:
            return

        self.close()

    def initialize(self) -> None:
        for pin in JIG_GPIO_CONFIG:
            if pin.direction == "in":
                self.backend.setup_input(pin.pin, pull=pin.pull)
            elif pin.direction == "out":
                assert pin.initial is not None
                self.backend.setup_output(pin.pin, initial=pin.initial)
            else:
                raise ValueError(
                    f"Unsupported GPIO direction for {pin.name}: {pin.direction}"
                )
        self._initialized = True

    def read(self, pin: int) -> bool:
        if not self._initialized:
            raise RuntimeError("GPIO is not initialized")
        return self.backend.read(pin)

    def write(self, pin: int, value: bool) -> None:
        if not self._initialized:
            raise RuntimeError("GPIO is not initialized")
        self.backend.write(pin, value)

    def write_named(self, name: str, value: bool) -> None:
        for pin in JIG_GPIO_CONFIG:
            if pin.name == name:
                self.write(pin.pin, value)
                return
        raise KeyError(f"Unknown JIG GPIO signal: {name}")

    def read_named(self) -> dict[str, bool]:
        return {pin.name: self.read(pin.pin) for pin in JIG_GPIO_CONFIG}

    def close(self) -> None:
        self.backend.close()
