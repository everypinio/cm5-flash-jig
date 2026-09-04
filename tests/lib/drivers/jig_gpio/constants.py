from dataclasses import dataclass

from tests.env import settings


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
OUT_EN = settings.DUT_POWER_ENABLE_GPIO
INA_ALERT = settings.DUT_POWER_ALERT_GPIO


JIG_GPIO_CONFIG = (
    # Keep DUT power disabled from the first configured output onward.
    PinConfig("OUT_EN", OUT_EN, "out", initial=False),
    PinConfig("INA_ALERT", INA_ALERT, "in", pull=None),
    PinConfig("DUT_PRESENT", DUT_PRESENT, "in", pull="up"),
    PinConfig("nRESET_OUT", NRESET_OUT, "out", initial=True),
    PinConfig("nRPI_BOOT", NRPI_BOOT, "out", initial=True),
    PinConfig("LED_nACT", LED_NACT, "in", pull=None),
    PinConfig("LED_nPWR", LED_NPWR, "in", pull=None),
    PinConfig("PWR_BUT", PWR_BUT, "out", initial=True),
)
