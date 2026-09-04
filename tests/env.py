from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

from tests.env_types import DevPath, FlexibleInt

DATADIR = Path(__file__).parent / "data"


class Settings(BaseSettings):
    # Power Write Control
    CM_FLASHER_ENABLE_POWER_WRITE: bool = False
    CM_FLASHER_ENABLE_FLASH_WRITE: bool = False
    CM_FLASHER_RPIBOOT_COMMAND: str = "rpiboot"
    CM_FLASHER_NO_RPIBOOT_SUDO: bool = False
    CM_FLASHER_RPIBOOT_DIR: Path | None = None
    CM_FLASHER_UART_DEVICE: DevPath = Path("/dev/ttyAMA0")
    CM_FLASHER_UART_BAUD: int = 115200
    CM_FLASHER_I2C_DEVICE: DevPath = Path("/dev/i2c-1")
    CM_FLASHER_DUT_PRESENT_TIMEOUT_S: float = 120.0
    CM_FLASHER_DUT_PRESENT_POLL_S: float = 0.25
    CM_FLASHER_RPIBOOT_TIMEOUT_S: int = 60
    CM_FLASHER_DEVICE_TIMEOUT_S: int = 60
    CM_FLASHER_DEVICE_POLL_S: float = 0.5
    CM_FLASHER_SKIP_RPIBOOT: bool = False
    CM_FLASHER_KEEP_MOUNTED: bool = False

    # DUT power subsystem. The onboard backend drives GPIO20 and measures
    # voltage/current with the INA229 fitted to the rev.2 main board.
    DUT_POWER_BACKEND: str = "onboard_ina229"
    DUT_POWER_NOMINAL_V: float = 5.0
    DUT_POWER_CURRENT_LIMIT_A: float = 3.0
    DUT_POWER_MIN_V: float = 4.75
    DUT_POWER_MAX_V: float = 5.25
    DUT_POWER_OFF_MAX_V: float = 0.5
    DUT_POWER_IDLE_CURRENT_MAX_A: float = 0.1
    DUT_POWER_ENABLE_GPIO: int = 20
    DUT_POWER_ALERT_GPIO: int = 21

    # INA229 SPI current/voltage monitor.
    INA229_SPI_BUS: int = 0
    INA229_SPI_DEVICE: int = 1
    INA229_SPI_MAX_HZ: int = 1_000_000
    INA229_SHUNT_OHMS: float = 0.01
    INA229_ADC_RANGE: int = 0
    INA229_CONVERSION_TIME_CODE: int = 3

    # PwrBlock settings for power smoke test.
    PWRBLOCK_CHANNEL: int = 0
    PWRBLOCK_TEST_VOLTAGE: float = 5.0
    PWRBLOCK_TEST_CURRENT: float = 3.0
    PWRBLOCK_TEST_MIN_VOLTAGE: float = 4.75
    PWRBLOCK_TEST_MAX_VOLTAGE: float = 5.25
    PWRBLOCK_DUT_VOLTAGE: float = 5.0
    PWRBLOCK_DUT_CURRENT: float = 3.0
    PWRBLOCK_DUT_MIN_VOLTAGE: float = 4.75
    PWRBLOCK_DUT_MAX_VOLTAGE: float = 5.25
    PWRBLOCK_RESOURCE: str | None = None
    PWRBLOCK_ENABLE_ENV: str = "CM_FLASHER_ENABLE_POWER_WRITE"
    PWRBLOCK_SETTLE_S: float = 0.5

    # ADS1015 power-rail measurements.
    ADC_MODEL: str = "ADS1015"
    ADC_I2C_BUS: int = 1
    ADC_I2C_ADDRESS: FlexibleInt = 0x48
    ADC_FULL_SCALE_V: float = 4.096
    ADC_5V_ENABLED: bool = True
    ADC_5V_CHANNEL: int = 2
    ADC_5V_SCALE: float = 2.0
    ADC_5V_MIN: float = 4.75
    ADC_5V_MAX: float = 5.25
    ADC_3V3_CHANNEL: int = 0
    ADC_3V3_SCALE: float = 1.0
    ADC_3V3_MIN: float = 3.135
    ADC_3V3_MAX: float = 3.465
    ADC_1V8_CHANNEL: int = 1
    ADC_1V8_SCALE: float = 1.0
    ADC_1V8_MIN: float = 1.71
    ADC_1V8_MAX: float = 1.89

    # Image and optional fallback target disk. In production the target found
    # after rpiboot takes precedence over this setting.
    CM_FLASHER_IMAGE: Path = Path.home() / "images" / "cm5-test.img.xz"
    CM_FLASHER_DEVICE: DevPath | None = None

    CM_FLASHER_GPIO_BACKEND: str | None = None

    # Standcloud integration
    HARDPY_SC_API_KEY: str | None = None
    HARDPY_USER_NAME: str
    HARDPY_DUT_NAME: str
    HARDPY_DUT_TYPE: str
    HARDPY_STAND_NAME: str
    HARDPY_STAND_LOCATION: str
    POWER_ON_HARDPY_USER_NAME: str
    POWER_ON_HARDPY_DUT_NAME: str
    POWER_ON_HARDPY_DUT_TYPE: str
    POWER_ON_HARDPY_STAND_NAME: str
    POWER_ON_HARDPY_DUT_PART_NUMBER: str = "CM5-FLASHER"
    POWER_ON_HARDPY_DUT_SERIAL_NUMBER: str | None = None
    POWER_ON_HARDPY_BATCH_SERIAL_NUMBER: str = "POWER-ON-SELFTEST"

    # DUT
    DUT_BOOT_LOG_DIR: Path = Path(".tmp/dut_boot_logs")
    DUT_USB_BOOT_LOG_DIR: Path = Path(".tmp/dut_usb_boot_logs")
    DUT_USB_BOOT_POWER_SETTLE_S: float = 0.5
    DUT_USB_BOOT_UART_POST_CAPTURE_S: float = 2.0
    DUT_BOOT_POWER_SETTLE_S: float = 1.0
    DUT_BOOT_TIMEOUT_S: float = 60.0
    DUT_BOOT_SUCCESS_PHRASE: str = "raspberrypi login:"
    DUT_BOOT_ACTIVITY_TIMEOUT_S: float = 45.0
    DUT_BOOT_ACTIVITY_POLL_S: float = 0.1
    DUT_BOOT_REQUIRE_LED_NPWR: bool = False
    DUT_BOOT_REQUIRE_LED_NACT: bool = False
    DUT_BOOT_REQUIRE_LED_NACT_TRANSITION: bool = False
    DUT_POWER_SETTLE_S: float = 1.0

    # Mocks
    MOCK_DISPLAY: bool = False
    MOCK_GPIO: bool = False
    MOCK_FLASHING: bool = True
    MOCK_PWRBLOCK: bool = False
    MOCK_INA229: bool = False
    MOCK_ADC: bool = False  # `True` is for dry lab runs

    # Optional: read from a .env file
    model_config = SettingsConfigDict(env_file=".env")


# Instantiate your settings
settings = Settings()
