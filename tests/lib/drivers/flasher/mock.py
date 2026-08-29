from pathlib import Path

from tests.env import settings
from .models import BlockDevice


def get_mock_block_device() -> BlockDevice:
    return BlockDevice(
        path=str(settings.CM_FLASHER_DEVICE),
        name="mock_sda",
        kind="disk",
        removable=False,
        size="32G",
        model="Mock eMMC",
        serial="1234567890",
        mountpoints=(),
        children=(),
    )


def list_block_devices() -> list[BlockDevice]:
    return [get_mock_block_device()]


def disk_by_path(devices: list[BlockDevice], path: str) -> BlockDevice | None:
    for device in devices:
        if device.path == str(path):
            return device
    return None


def describe_device(device: BlockDevice) -> str:
    return f"{device.model or 'Unknown'} ({device.size})"


def validate_target_device(device: BlockDevice) -> None:
    pass


def unmount_device(device: BlockDevice, *, dry_run: bool) -> None:
    pass


def write_image(image: Path, device: BlockDevice, *, dry_run: bool) -> None:
    pass
