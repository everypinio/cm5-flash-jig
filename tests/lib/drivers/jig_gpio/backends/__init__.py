from tests.env import settings

from ..interfaces import GPIOBackend
from .exceptions import GPIOBackendUnavailable
from .gpiozero import GpiozeroBackend
from .pinctrl import PinctrlBackend
from .raspi_gpio import RaspiGpioBackend
from .rpi_gpio import RPiGPIOBackend


def make_gpio_backend(preferred: str | None = None) -> GPIOBackend:
    preferred = (preferred or settings.CM_FLASHER_GPIO_BACKEND or "auto").lower()
    errors: list[str] = []

    # Raspberry Pi 5 and 4

    # The recommended, high-level, object-oriented Python library
    # for controlling hardware pins on a Raspberry Pi.

    # Backends:
    # - lgpio:      The default and modern backend utilized for recent hardware like the Raspberry Pi 5,
    #               interfacing directly with Linux gpiochip devices.
    # - RPi.GPIO:   The classic, lightweight backend traditionally used on older Raspberry Pi models.
    # - pigpio:     Advanced backend supporting hardware-timed pulses and remote network control over a daemon.
    # - native:     Pure Python implementation communicating straight through the Linux sysfs or memory maps without heavy external dependencies
    # - mock:       Simulated factory used for testing code logic without real hardware attached.

    if preferred in {"auto", "gpiozero"}:
        try:
            return GpiozeroBackend()
        except Exception as exc:
            errors.append(f"gpiozero: {exc}")
            if preferred == "gpiozero":
                raise GPIOBackendUnavailable("; ".join(errors)) from exc

    # Fully maintained, works across all board generations (including Pi 5),
    # and handles advanced pin multiplexing and direct hardware configurations.
    if preferred in {"auto", "pinctrl"}:
        try:
            return PinctrlBackend()
        except Exception as exc:
            errors.append(f"pinctrl: {exc}")
            if preferred == "pinctrl":
                raise GPIOBackendUnavailable("; ".join(errors)) from exc

    # Raspberry Pi 4 only

    # An older, low-level legacy Python library.
    # It does not support newer hardware like the Raspberry Pi 5.
    if preferred in {"auto", "rpi.gpio", "rpi_gpio"}:
        try:
            return RPiGPIOBackend()
        except Exception as exc:
            errors.append(f"RPi.GPIO: {exc}")
            if preferred in {"rpi.gpio", "rpi_gpio"}:
                raise GPIOBackendUnavailable("; ".join(errors)) from exc

    # raspi-gpio: Deprecated and unmaintained legacy tool primarily used on older models like the Pi 4.
    if preferred in {"auto", "raspi-gpio", "raspi_gpio"}:
        try:
            return RaspiGpioBackend()
        except Exception as exc:
            errors.append(f"raspi-gpio: {exc}")
            if preferred in {"raspi-gpio", "raspi_gpio"}:
                raise GPIOBackendUnavailable("; ".join(errors)) from exc

    details = "; ".join(errors) if errors else f"unknown backend: {preferred}"
    raise GPIOBackendUnavailable(f"No supported GPIO backend is available ({details})")
