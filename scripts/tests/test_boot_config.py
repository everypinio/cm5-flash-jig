import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.lib.drivers.flasher import boot_config as config
from tests.lib.drivers.flasher.models import BlockDevice, FlashError


class BootConfigTests(unittest.TestCase):
    def test_config_preserves_image_settings_and_is_idempotent(self):
        original = "[cm5]\ndtoverlay=dwc2,dr_mode=host\n[all]\narm_64bit=1\n"
        result = config.cm4_uart_config(original)
        self.assertTrue(result.startswith(original))
        self.assertIn("[cm4]\nenable_uart=1\ndtoverlay=disable-bt\nuart_2ndstage=1\n[all]", result)
        self.assertEqual(config.cm4_uart_config(result), result)

    def test_incomplete_managed_block_is_rejected(self):
        with self.assertRaises(FlashError):
            config.cm4_uart_config(config.BEGIN + "\n[cm4]\n")

    def test_post_flash_mount_write_verify_and_unmount(self):
        device = BlockDevice("/dev/sda", "sda", "disk", True, "8G", None, None, (), ())
        with tempfile.TemporaryDirectory() as directory:
            mount = Path(directory) / "mount"
            mount.mkdir()
            calls = []
            written = {}

            def run(args, *, input=None):
                calls.append(args)
                if "lsblk" in args:
                    self.assertIn("--tree", args)
                    return json.dumps({"blockdevices": [{"path": "/dev/sda", "children": [
                        {"path": "/dev/sda1", "type": "part", "fstype": "vfat"},
                        {"path": "/dev/sda2", "type": "part", "fstype": "ext4"},
                    ]}]})
                if "mount" in args:
                    (mount / "config.txt").write_text("[all]\narm_64bit=1\n")
                    (mount / "cmdline.txt").write_text("console=tty1 root=PARTUUID=123 rootwait\n")
                if "tee" in args:
                    Path(args[-1]).write_text(input)
                    written[Path(args[-1]).name] = input
                if "umount" in args:
                    # Simulate the mount disappearing, leaving its directory empty.
                    for file in mount.iterdir():
                        file.unlink()
                return ""

            with patch.object(config.real, "list_block_devices", return_value=[device]), \
                 patch.object(config.real, "unmount_device"), \
                 patch.object(config.tempfile, "mkdtemp", return_value=str(mount)), \
                 patch.object(config, "_run", side_effect=run):
                self.assertEqual(config.configure_cm4_uart(device), "/dev/sda1")
            self.assertIn("uart_2ndstage=1", written["config.txt"])
            self.assertEqual(written["cmdline.txt"], "console=serial0,115200 console=tty1 root=PARTUUID=123 rootwait\n")
            self.assertTrue(any("cp" in call for call in calls))
            self.assertEqual(calls[-1], ["sudo", "-n", "umount", str(mount)])
            self.assertFalse(mount.exists())

    def test_host_disk_rejected_before_any_command(self):
        device = BlockDevice("/dev/mmcblk0", "mmcblk0", "disk", False, "64G", None, None, (), ())
        with patch.object(config, "_run") as run:
            with self.assertRaises(FlashError):
                config.configure_cm4_uart(device)
            run.assert_not_called()

    def test_ambiguous_boot_partitions_are_rejected_before_mount(self):
        device = BlockDevice("/dev/sda", "sda", "disk", True, "8G", None, None, (), ())
        listing = json.dumps({"blockdevices": [{"path": device.path, "children": [
            {"path": "/dev/sda1", "type": "part", "fstype": "vfat"},
            {"path": "/dev/sda2", "type": "part", "fstype": "vfat"},
        ]}]})
        with patch.object(config.real, "list_block_devices", return_value=[device]), \
             patch.object(config.real, "unmount_device"), \
             patch.object(config, "_run", return_value=listing) as run, \
             patch.object(config.tempfile, "mkdtemp") as mount:
            with self.assertRaisesRegex(FlashError, "exactly one"):
                config.configure_cm4_uart(device)
            mount.assert_not_called()
            self.assertFalse(any("tee" in call.args[0] for call in run.call_args_list))


if __name__ == "__main__":
    unittest.main()
