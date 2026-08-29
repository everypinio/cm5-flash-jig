from typing import Any

from tests.env import settings

import hardpy
import pytest

from tests.lib.drivers.display.dfr0997_operator_panel import (
    DFR0997Display,
    DFR0997OperatorPanel,
)

failed_display_step: str | None = None


def _hardpy_enabled(config: pytest.Config) -> bool:
    return bool(getattr(config.option, "hardpy_pt", False))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[Any]):
    global failed_display_step

    outcome = yield
    report = outcome.get_result()
    if not report.failed or failed_display_step is not None:
        return

    marker = item.get_closest_marker("case_name")
    if marker and marker.args:
        failed_display_step = str(marker.args[0])
    else:
        failed_display_step = item.name


def _show_final_fail_on_display() -> None:
    if failed_display_step is None:
        return

    with DFR0997Display() as display_driver:
        display = DFR0997OperatorPanel(display=display_driver)
        try:
            display.show_fail(failed_display_step)
        except Exception as exc:
            print(f"Could not show final FAIL on DFR0997 display: {exc}")


def _show_final_pass_on_display() -> None:
    with DFR0997Display() as display_driver:
        display = DFR0997OperatorPanel(display=display_driver)
        try:
            display.show_pass()
        except Exception as exc:
            print(f"Could not show final PASS on DFR0997 display: {exc}")


def finish_executing():
    if failed_display_step is None:
        _show_final_pass_on_display()
    else:
        _show_final_fail_on_display()
    print("Testing completed")


@pytest.fixture(scope="session", autouse=True)
def fill_actions_after_test(request: pytest.FixtureRequest):
    try:
        post_run_functions = request.getfixturevalue("post_run_functions")
    except pytest.FixtureLookupError:
        yield
        return

    post_run_functions.append(finish_executing)
    yield


@pytest.fixture(scope="session", autouse=True)
def set_hardpy_testplan_metadata(request: pytest.FixtureRequest):
    if _hardpy_enabled(request.config) and not request.config.option.collectonly:
        hardpy.set_user_name(settings.HARDPY_USER_NAME)
        hardpy.set_dut_name(settings.HARDPY_DUT_NAME)
        hardpy.set_dut_type(settings.HARDPY_DUT_TYPE)
        hardpy.set_stand_name(settings.HARDPY_STAND_NAME)

    yield


@pytest.fixture(scope="session")
def display_panel():
    """
    Provides an initialized OperatorPanel.
    The underlying DFR0997Display automatically switches between real hardware
    and mock implementation based on settings.MOCK_DISPLAY.
    """
    with DFR0997Display() as raw_driver:
        yield DFR0997OperatorPanel(display=raw_driver)


@pytest.fixture(scope="session")
def gpio_controller(request: pytest.FixtureRequest):
    from tests.lib.drivers.jig_gpio import JigGPIO, JigGPIOController, GPIOBackendUnavailable
    try:
        gpio = JigGPIO()
        controller = JigGPIOController(gpio)
    except GPIOBackendUnavailable as exc:
        if _hardpy_enabled(request.config):
            pytest.fail(str(exc))
        pytest.skip(str(exc))

    with gpio:
        yield controller


@pytest.fixture(scope="session")
def power_block(request: pytest.FixtureRequest):
    from tests.imports import load_power_module
    power_module = load_power_module(request)
    if not power_module:
        pytest.skip("No Power module available")
    resource_name = settings.PWRBLOCK_RESOURCE
    driver = power_module.PowerBlockDriver(resource_name=resource_name)
    driver.connect()
    try:
        yield driver
    finally:
        driver.disconnect()


@pytest.fixture(scope="session")
def adc_reader(request: pytest.FixtureRequest):
    from tests.imports import load_ads_module

    if settings.MOCK_ADC:
        yield None
        return

    ads_module = load_ads_module(request)
    if not ads_module:
        pytest.skip("No ADS module available")

    with ads_module.ADS1x15Reader(
        address=settings.ADC_I2C_ADDRESS,
        bus_id=settings.ADC_I2C_BUS,
        full_scale_v=settings.ADC_FULL_SCALE_V,
        model=settings.ADC_MODEL,
    ) as adc:
        yield adc

HOLD_POWER_KEY = pytest.StashKey[bool]()

@pytest.fixture(scope="module", autouse=True)
def _module_power_safety(power_block):
    """Safety net: Always turn off power at the end of the test module."""
    yield
    try:
        power_block.set_supply(settings.PWRBLOCK_CHANNEL, "OFF")
    except Exception:
        pass

@pytest.fixture(scope="function", autouse=True)
def _function_power_safety(request, power_block):
    """Safety net: Turn off power at the end of the test, unless held."""
    yield
    
    # 1. Did the test itself request a dynamic hold?
    if request.node.stash.get(HOLD_POWER_KEY, False):
        return
        
    # 2. Did the module (or function) request a static hold via marker?
    if "hold_power_for_module" in request.keywords:
        return
        
    # 3. Default: Turn it off safely
    try:
        power_block.set_supply(settings.PWRBLOCK_CHANNEL, "OFF")
    except Exception:
        pass
