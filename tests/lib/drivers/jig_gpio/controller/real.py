from ..constants import DUT_PRESENT, JIG_GPIO_CONFIG
from ..gpio import JigGPIO
from ..interfaces import JigGPIOControllerInterface


class JigGPIOControllerImpl(JigGPIOControllerInterface):
    """Real implementation of JigGPIOControllerInterface using JigGPIO."""

    def __init__(self, gpio: JigGPIO) -> None:
        self.gpio = gpio
        self._last_dut_present: bool | None = None

    def is_dut_present(self) -> bool:
        # DUT_PRESENT is active low (LOW = present)
        raw_level = self.gpio.read(DUT_PRESENT)
        dut_present = not raw_level
        if dut_present != self._last_dut_present:
            print(
                f"DUT_PRESENT GPIO{DUT_PRESENT}: "
                f"raw={'HIGH' if raw_level else 'LOW'}, "
                f"logical={'present' if dut_present else 'not present'}",
                flush=True,
            )
            self._last_dut_present = dut_present
        return dut_present

    def set_boot_mode(self, active: bool) -> None:
        # nRPI_BOOT is active low (False/LOW = boot mode active)
        self.gpio.write_named("nRPI_BOOT", not active)

    def is_boot_mode_active(self) -> bool:
        # nRPI_BOOT is active low
        return not self.gpio.read_named()["nRPI_BOOT"]

    def is_led_active(self, led_name: str) -> bool:
        # LEDs are active low
        for pin in JIG_GPIO_CONFIG:
            if pin.name == led_name:
                return not self.gpio.read(pin.pin)
        raise KeyError(f"Unknown LED signal: {led_name}")

    def get_all_states(self) -> dict[str, bool]:
        return self.gpio.read_named()

    def read_pin(self, pin: int) -> bool:
        return self.gpio.read(pin)
