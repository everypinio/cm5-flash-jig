from gpiozero import Device
from gpiozero.pins.mock import MockFactory

from tests.env import settings

if settings.MOCK_GPIO:
    Device.pin_factory = MockFactory


class GpiozeroBackend:
    name = "gpiozero"

    def __init__(self) -> None:
        from gpiozero import DigitalInputDevice, DigitalOutputDevice

        self._digital_input_device = DigitalInputDevice
        self._digital_output_device = DigitalOutputDevice
        self._devices: dict[int, DigitalInputDevice | DigitalOutputDevice] = {}

    def setup_input(self, pin: int, *, pull: str | None) -> None:
        pull_up = pull == "up"
        self._devices[pin] = self._digital_input_device(pin, pull_up=pull_up)

    def setup_output(self, pin: int, *, initial: bool) -> None:
        self._devices[pin] = self._digital_output_device(
            pin,
            active_high=True,
            initial_value=initial,
        )

    def read(self, pin: int) -> bool:
        return bool(self._devices[pin].pin.state)

    def write(self, pin: int, value: bool) -> None:
        device = self._devices[pin]

        if not isinstance(device, self._digital_output_device):
            raise RuntimeError()

        device.value = int(value)

    def close(self) -> None:
        for device in self._devices.values():
            device.close()
