"""Configure the freshly flashed DUT boot partition before normal boot."""

import json
import subprocess
import tempfile
import time
from pathlib import Path

from . import real
from .models import BlockDevice, FlashError

BEGIN = "# BEGIN cm5-flash-jig CM4 UART"
END = "# END cm5-flash-jig CM4 UART"


def cm4_uart_config(text: str) -> str:
    """Keep image settings and append one authoritative, CM4-only block."""
    if BEGIN in text:
        before, rest = text.split(BEGIN, 1)
        if END not in rest:
            raise FlashError("Incomplete managed UART block in config.txt")
        _, after = rest.split(END, 1)
        text = before + after
    return text.rstrip() + (
        f"\n\n{BEGIN}\n[cm4]\nenable_uart=1\ndtoverlay=disable-bt\n"
        f"uart_2ndstage=1\n[all]\n{END}\n"
    )


def _run(args: list[str], *, input: str | None = None) -> str:
    result = subprocess.run(
        args, input=input, text=True, capture_output=True, timeout=60, check=True
    )
    return result.stdout


def configure_cm4_uart(device: BlockDevice) -> str:
    """Update only the selected DUT; fail the flash step if configuration fails."""
    real.validate_target_device(device)
    current = real.disk_by_path(real.list_block_devices(), device.path)
    if current is None:
        raise FlashError("DUT disappeared before UART configuration")
    real.validate_target_device(current)
    real.unmount_device(current, dry_run=False)
    _run(["sudo", "-n", "blockdev", "--rereadpt", device.path])
    _run(["sudo", "-n", "udevadm", "settle"])
    deadline = time.monotonic() + 15
    while True:
        data = json.loads(_run([
            "sudo", "-n", "lsblk", "--json", "--tree", "--output",
            "NAME,PATH,TYPE,FSTYPE", device.path,
        ]))
        disks = data.get("blockdevices", [])
        if len(disks) != 1 or disks[0].get("path") != device.path:
            raise FlashError("Unexpected DUT partition listing")
        candidates = [
            part["path"] for part in disks[0].get("children", [])
            if part.get("type") == "part" and part.get("fstype") == "vfat"
        ]
        if len(candidates) == 1:
            break
        if len(candidates) > 1 or time.monotonic() >= deadline:
            raise FlashError("Expected exactly one FAT boot partition on DUT")
        time.sleep(0.25)

    # Recheck desktop automounts after the partition table has been refreshed.
    current = real.disk_by_path(real.list_block_devices(), device.path)
    if current is None:
        raise FlashError("DUT disappeared before mounting boot partition")
    real.validate_target_device(current)
    real.unmount_device(current, dry_run=False)
    mount = Path(tempfile.mkdtemp(prefix="cm-flasher-boot-"))
    mounted = False
    try:
        _run(["sudo", "-n", "mount", "-o", "nosuid,nodev,noexec", candidates[0], str(mount)])
        mounted = True
        config = mount / "config.txt"
        cmdline = mount / "cmdline.txt"
        original = config.read_text(encoding="utf-8")
        command = cmdline.read_text(encoding="utf-8")
        updated = cm4_uart_config(original)
        # Keep the display console and all root filesystem arguments intact.
        tokens = command.split()
        tokens = [t for t in tokens if not t.startswith("console=serial0,")]
        tokens.insert(0, "console=serial0,115200")
        for path, old, new in (
            (config, original, updated),
            (cmdline, command, " ".join(tokens) + "\n"),
        ):
            if old == new:
                continue
            backup = path.with_name(path.name + ".before-jig-uart")
            if not backup.exists():
                _run(["sudo", "-n", "cp", "--", str(path), str(backup)])
            _run(["sudo", "-n", "tee", str(path)], input=new)
            if path.read_text(encoding="utf-8") != new:
                raise FlashError(f"UART configuration readback failed: {path.name}")
        _run(["sync"])
    finally:
        # Never recursively clean up a directory that may still be mounted.
        if mounted:
            _run(["sudo", "-n", "umount", str(mount)])
        mount.rmdir()
    return candidates[0]
