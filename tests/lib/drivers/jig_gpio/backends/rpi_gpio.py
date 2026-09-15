class RPiGPIOBackend:
    name = "RPi.GPIO"

    def __init__(self) -> None:
        import RPi.GPIO as GPIO

        self._gpio = GPIO
        self._claimed: list[int] = []
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

    def setup_input(self, pin: int, *, pull: str | None) -> None:
        pud = self._gpio.PUD_UP if pull == "up" else self._gpio.PUD_OFF
        self._gpio.setup(pin, self._gpio.IN, pull_up_down=pud)
        self._claimed.append(pin)

    def setup_output(self, pin: int, *, initial: bool) -> None:
        level = self._gpio.HIGH if initial else self._gpio.LOW
        self._gpio.setup(pin, self._gpio.OUT, initial=level)
        self._claimed.append(pin)

    def read(self, pin: int) -> bool:
        return bool(self._gpio.input(pin))

    def write(self, pin: int, value: bool) -> None:
        level = self._gpio.HIGH if value else self._gpio.LOW
        self._gpio.output(pin, level)

    def close(self) -> None:
        if self._claimed:
            self._gpio.cleanup(self._claimed)
