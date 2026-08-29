"""Flash a Raspberry Pi CM4/CM5 eMMC over USB boot.

Expected JIG flow:
1. Hold nRPIBOOT low and connect CM5 USB D+/D- to the host Raspberry Pi.
2. Run rpiboot so the DUT eMMC appears as a USB mass-storage block device.
3. Write the requested image to the newly appeared block device.

The write step is intentionally guarded by --yes because it destroys the target
block device contents.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import BlockDevice, FlashError


DEFAULT_LSBLK_COLUMNS = "NAME,PATH,TYPE,RM,SIZE,MODEL,SERIAL,MOUNTPOINTS"
DEFAULT_WRITE_BLOCK_SIZE = "4M"
PROTECTED_MOUNTPOINTS = {"/", "/boot", "/boot/firmware", "[SWAP]"}


def _command_output(stdout: str | bytes | None, stderr: str | bytes | None) -> str:
    def decode(value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode(errors="replace")
        return value

    return (decode(stdout) + decode(stderr)).strip()


def run_command(
    argv: list[str],
    *,
    check: bool = True,
    capture: bool = True,
    timeout_s: int | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        check=check,
        capture_output=capture,
        text=True,
        timeout=timeout_s,
    )


def normalize_mountpoints(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    return tuple(item for item in value if item)


def parse_block_device(raw: dict[str, Any]) -> BlockDevice:
    return BlockDevice(
        path=raw.get("path") or f"/dev/{raw['name']}",
        name=raw["name"],
        kind=raw.get("type") or "",
        removable=bool(raw.get("rm")),
        size=raw.get("size") if isinstance(raw.get("size"), int) else None,
        model=raw.get("model"),
        serial=raw.get("serial"),
        mountpoints=normalize_mountpoints(raw.get("mountpoints")),
        children=tuple(parse_block_device(child) for child in raw.get("children", [])),
    )


def list_block_devices() -> list[BlockDevice]:
    result = run_command(
        ["lsblk", "-J", "-b", "-o", DEFAULT_LSBLK_COLUMNS],
        timeout_s=10,
    )
    data = json.loads(result.stdout)
    return [parse_block_device(item) for item in data.get("blockdevices", [])]


def flatten_devices(devices: list[BlockDevice]) -> list[BlockDevice]:
    flat: list[BlockDevice] = []
    for device in devices:
        flat.append(device)
        flat.extend(flatten_devices(list(device.children)))
    return flat


def disk_by_path(devices: list[BlockDevice], path: str) -> BlockDevice | None:
    for device in flatten_devices(devices):
        if device.path == str(path) and device.kind == "disk":
            return device
    return None


def describe_device(device: BlockDevice) -> str:
    size = f"{device.size} bytes" if device.size is not None else "unknown size"
    model = device.model or "unknown model"
    serial = device.serial or "no serial"
    mounts = ", ".join(device.child_mountpoints) or "not mounted"
    return f"{device.path} ({size}, {model}, {serial}, {mounts})"


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise FlashError(f"Required tool is missing: {name}")
    return path


def run_rpiboot(command: str, timeout_s: int, *, use_sudo: bool, boot_dir: str | None) -> None:
    if shutil.which(command) is None:
        raise FlashError(
            f"Required tool is missing: {command}. Install raspberrypi usbboot/rpiboot on the host."
        )

    argv = [command]
    if boot_dir:
        argv.extend(["-d", boot_dir])
    if use_sudo:
        require_tool("sudo")
        argv.insert(0, "sudo")

    try:
        result = run_command(argv, check=False, timeout_s=timeout_s)
    except subprocess.TimeoutExpired as exc:
        output = _command_output(exc.stdout, exc.stderr)
        suffix = f": {output}" if output else ""
        raise FlashError(f"{command} timed out after {timeout_s} seconds{suffix}") from exc

    if result.returncode != 0:
        output = _command_output(result.stdout, result.stderr)
        raise FlashError(f"{command} failed with code {result.returncode}: {output}")


def wait_for_new_disk(
    before_paths: set[str],
    *,
    timeout_s: int,
    poll_s: float,
) -> BlockDevice:
    deadline = time.monotonic() + timeout_s
    last_candidates: list[BlockDevice] = []

    while time.monotonic() < deadline:
        disks = [device for device in list_block_devices() if device.kind == "disk"]
        candidates = [
            device
            for device in disks
            if device.path not in before_paths
            and not device.has_mounts
            and not device.path.startswith("/dev/loop")
            and not device.path.startswith("/dev/zram")
        ]
        last_candidates = candidates
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            details = "\n".join(f"- {describe_device(device)}" for device in candidates)
            raise FlashError(f"More than one new disk appeared. Refusing to guess:\n{details}")
        time.sleep(poll_s)

    details = "\n".join(f"- {describe_device(device)}" for device in last_candidates)
    suffix = f" Last candidates:\n{details}" if details else ""
    raise FlashError(f"Timed out waiting for the DUT USB mass-storage disk.{suffix}")


def candidate_disks(devices: list[BlockDevice]) -> list[BlockDevice]:
    return [
        device
        for device in devices
        if device.kind == "disk"
        and not device.path.startswith("/dev/mmcblk")
        and not device.path.startswith("/dev/loop")
        and not device.path.startswith("/dev/zram")
    ]


def choose_existing_usb_disk(devices: list[BlockDevice]) -> BlockDevice:
    candidates = [
        device
        for device in candidate_disks(devices)
        if not any(mount in PROTECTED_MOUNTPOINTS for mount in device.child_mountpoints)
    ]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise FlashError("No existing USB target disk found. Use --device or run without --skip-rpiboot.")
    details = "\n".join(f"- {describe_device(device)}" for device in candidates)
    raise FlashError(f"More than one existing USB target disk found. Use --device:\n{details}")


def validate_target_device(device: BlockDevice) -> None:
    protected = PROTECTED_MOUNTPOINTS.intersection(device.child_mountpoints)
    if protected:
        raise FlashError(f"Refusing to use system disk {device.path}; protected mounts: {sorted(protected)}")
    if device.path.startswith("/dev/mmcblk") or device.path.startswith("/dev/zram"):
        raise FlashError(f"Refusing to use protected host device: {device.path}")


def unmount_device(device: BlockDevice, *, dry_run: bool) -> None:
    for mountpoint in device.child_mountpoints:
        if dry_run:
            print(f"DRY RUN: sudo umount {mountpoint}")
        else:
            run_command(["sudo", "umount", mountpoint], capture=True, timeout_s=30)


def image_reader_command(image: Path) -> list[str] | None:
    suffixes = "".join(image.suffixes[-2:])
    if image.suffix == ".xz" or suffixes.endswith(".img.xz"):
        require_tool("xz")
        return ["xz", "-dc", str(image)]
    if image.suffix == ".gz" or suffixes.endswith(".img.gz"):
        require_tool("gzip")
        return ["gzip", "-dc", str(image)]
    return None


def write_image(image: Path, device: BlockDevice, *, dry_run: bool) -> None:
    require_tool("dd")
    image = image.expanduser().resolve()
    if not image.exists():
        raise FlashError(f"Image does not exist: {image}")
    if not image.is_file():
        raise FlashError(f"Image path is not a file: {image}")

    reader = image_reader_command(image)
    dd_cmd = [
        "sudo",
        "dd",
        f"of={device.path}",
        f"bs={DEFAULT_WRITE_BLOCK_SIZE}",
        "conv=fsync",
        "status=progress",
    ]

    if dry_run:
        source = " ".join(reader) if reader else str(image)
        print(f"DRY RUN: write {source} to {device.path}")
        print(f"DRY RUN: {' '.join(dd_cmd)}")
        return

    if reader:
        reader_proc = subprocess.Popen(reader, stdout=subprocess.PIPE)
        assert reader_proc.stdout is not None
        dd_proc = subprocess.Popen(dd_cmd, stdin=reader_proc.stdout)
        reader_proc.stdout.close()
        dd_code = dd_proc.wait()
        reader_code = reader_proc.wait()
        if reader_code != 0:
            raise FlashError(f"Image decompressor failed with code {reader_code}")
        if dd_code != 0:
            raise FlashError(f"dd failed with code {dd_code}")
    else:
        with image.open("rb") as image_file:
            dd_proc = subprocess.run(dd_cmd, stdin=image_file)
        if dd_proc.returncode != 0:
            raise FlashError(f"dd failed with code {dd_proc.returncode}")

    run_command(["sync"], capture=True, timeout_s=120)


def make_display(enabled: bool):
    if not enabled:
        return None
    try:
        from lib.dfr0997_display import DFR0997Display

        return DFR0997Display()
    except Exception as exc:
        print(f"Display disabled: {exc}", file=sys.stderr)
        return None


def display_call(display, method: str, *args: str) -> None:
    if display is None:
        return
    try:
        getattr(display, method)(*args)
    except Exception as exc:
        print(f"Display update failed: {exc}", file=sys.stderr)


def flash_cm5(args: argparse.Namespace) -> int:
    display = make_display(args.display)
    try:
        display_call(display, "show_flashing")

        require_tool("lsblk")
        before = list_block_devices()
        before_paths = {device.path for device in before if device.kind == "disk"}

        if args.device:
            current = list_block_devices()
            target = disk_by_path(current, args.device)
            if target is None:
                raise FlashError(f"Requested target disk was not found: {args.device}")
        else:
            if args.skip_rpiboot:
                target = choose_existing_usb_disk(list_block_devices())
            else:
                print("Running rpiboot...")
                run_rpiboot(
                    args.rpiboot_command,
                    args.rpiboot_timeout,
                    use_sudo=not args.no_rpiboot_sudo,
                    boot_dir=args.rpiboot_dir,
                )
                print("Waiting for DUT USB mass-storage disk...")
                target = wait_for_new_disk(
                    before_paths,
                    timeout_s=args.device_timeout,
                    poll_s=args.poll_interval,
                )

        print(f"Target: {describe_device(target)}")
        validate_target_device(target)
        if target.has_mounts:
            if args.keep_mounted:
                raise FlashError(f"Target has mounted filesystems: {target.child_mountpoints}")
            unmount_device(target, dry_run=args.dry_run)

        if not args.yes and not args.dry_run:
            raise FlashError("Refusing to write without --yes")

        write_image(args.image, target, dry_run=args.dry_run)
        display_call(display, "show_pass")
        print("Flash step completed.")
        return 0
    except FlashError as exc:
        display_call(display, "show_fail", str(exc)[:24])
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if display is not None:
            display.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Flash Raspberry Pi CM4/CM5 eMMC over USB.")
    parser.add_argument("--image", required=True, type=Path, help="Raw .img, .img.xz, or .img.gz file.")
    parser.add_argument("--device", help="Explicit target disk, for example /dev/sda.")
    parser.add_argument("--yes", action="store_true", help="Actually write the image to the target disk.")
    parser.add_argument("--dry-run", action="store_true", help="Detect target and print commands without writing.")
    parser.add_argument("--display", action="store_true", help="Show FLASHING/PASS/FAIL on DFR0997 display.")
    parser.add_argument("--skip-rpiboot", action="store_true", help="Do not run rpiboot before detection.")
    parser.add_argument("--rpiboot-command", default="rpiboot", help="rpiboot executable name/path.")
    parser.add_argument("--rpiboot-dir", help="Optional rpiboot boot directory, for example mass-storage-gadget.")
    parser.add_argument("--no-rpiboot-sudo", action="store_true", help="Run rpiboot without sudo.")
    parser.add_argument("--rpiboot-timeout", type=int, default=60, help="Seconds to wait for rpiboot.")
    parser.add_argument("--device-timeout", type=int, default=30, help="Seconds to wait for new USB disk.")
    parser.add_argument("--poll-interval", type=float, default=0.5, help="Block-device polling interval.")
    parser.add_argument(
        "--keep-mounted",
        action="store_true",
        help="Fail if target filesystems are mounted instead of unmounting them.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return flash_cm5(args)


if __name__ == "__main__":
    raise SystemExit(main())
