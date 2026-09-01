from pathlib import Path

import pytest

import tests.test_2_cm_flashing as flashing_tests
from tests.lib.drivers.flasher.models import BlockDevice, FlashError
from tests.lib.drivers.flasher.real import validate_target_device


def _disk(path: str, *mountpoints: str) -> BlockDevice:
    return BlockDevice(
        path=path,
        name=Path(path).name,
        kind="disk",
        removable=False,
        size="32G",
        model=None,
        serial=None,
        mountpoints=tuple(mountpoints),
        children=(),
    )


def test_detected_dut_disk_takes_precedence(monkeypatch) -> None:
    monkeypatch.setattr(flashing_tests.settings, "CM_FLASHER_DEVICE", Path("/dev/sdz"))
    monkeypatch.setattr(flashing_tests, "DETECTED_DUT_DEVICE", "/dev/sda")

    assert flashing_tests._target_device_path() == Path("/dev/sda")


def test_configured_disk_is_only_a_fallback(monkeypatch) -> None:
    monkeypatch.setattr(flashing_tests.settings, "CM_FLASHER_DEVICE", Path("/dev/sdz"))
    monkeypatch.setattr(flashing_tests, "DETECTED_DUT_DEVICE", None)

    assert flashing_tests._target_device_path() == Path("/dev/sdz")


def test_target_is_unknown_without_detection_or_fallback(monkeypatch) -> None:
    monkeypatch.setattr(flashing_tests.settings, "CM_FLASHER_DEVICE", None)
    monkeypatch.setattr(flashing_tests, "DETECTED_DUT_DEVICE", None)

    assert flashing_tests._target_device_path() is None


def test_host_mmc_device_is_never_a_flash_target() -> None:
    with pytest.raises(FlashError, match="protected host device"):
        validate_target_device(_disk("/dev/mmcblk0"))


def test_root_mounted_disk_is_never_a_flash_target() -> None:
    with pytest.raises(FlashError, match="system disk"):
        validate_target_device(_disk("/dev/sda", "/"))
