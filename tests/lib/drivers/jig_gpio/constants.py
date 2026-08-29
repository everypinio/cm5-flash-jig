from dataclasses import dataclass


@dataclass(frozen=True)
class PinConfig:
    name: str
    pin: int
    direction: str
    pull: str | None = None
    initial: bool | None = None


DUT_PRESENT = 26
NRESET_OUT = 19
NRPI_BOOT = 13
LED_NACT = 22
LED_NPWR = 27
PWR_BUT = 17


JIG_GPIO_CONFIG = (
    PinConfig("DUT_PRESENT", DUT_PRESENT, "in", pull="up"),
    PinConfig("nRESET_OUT", NRESET_OUT, "out", initial=True),
    PinConfig("nRPI_BOOT", NRPI_BOOT, "out", initial=True),
    PinConfig("LED_nACT", LED_NACT, "in", pull=None),
    PinConfig("LED_nPWR", LED_NPWR, "in", pull=None),
    PinConfig("PWR_BUT", PWR_BUT, "out", initial=True),
)
