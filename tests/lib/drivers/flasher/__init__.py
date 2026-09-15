from tests.env import settings
from .models import BlockDevice, FlashError

if settings.MOCK_FLASHING:
    from . import mock as module
else:
    from . import real as module

list_block_devices = module.list_block_devices
disk_by_path = module.disk_by_path
describe_device = module.describe_device
validate_target_device = module.validate_target_device
unmount_device = module.unmount_device
write_image = module.write_image

__all__ = [
    "BlockDevice",
    "FlashError",
    "list_block_devices",
    "disk_by_path",
    "describe_device",
    "validate_target_device",
    "unmount_device",
    "write_image",
]
