"""Record parsed CM5 DUT metadata in HardPy without duplicating identity fields."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_SERIAL_NUMBER_SET = False
_DUT_REVISION_SET = False
_DUT_PART_NUMBER_SET = False


_BOOT_INFO_TO_DUT_INFO = {
    "MODEL": "model",
    "EMMC_CID": "emmc_cid",
    "EMMC model": "emmc_model",
    "EMMC size GiB": "emmc_size_gib",
    "MAC": "mac",
    "IP address": "ip_address",
    "Hostname": "hostname",
    "Linux version": "linux_version",
    "BOOTLOADER release VERSION": "bootloader_version",
    "BOOTLOADER release DATE": "bootloader_date",
    "BOOTLOADER release TIME": "bootloader_time",
    "BOOTSYS release VERSION": "bootsys_version",
    "BOOTSYS release DATE": "bootsys_date",
    "BOOTSYS release TIME": "bootsys_time",
    "RPIBOOT release VERSION": "rpiboot_version",
    "RPIBOOT release DATE": "rpiboot_date",
    "RPIBOOT release TIME": "rpiboot_time",
    "BOOTMODE": "bootmode",
    "Boot mode": "boot_mode",
    "MFG_VER": "mfg_ver",
    "EEPROM ID": "eeprom_id",
    "RP1_BOOT chip ID": "rp1_boot_chip_id",
}


def build_dut_info_payload(
    boot_info: Mapping[str, str],
    variant_info: Mapping[str, Any],
) -> dict[str, str | int | float | None]:
    payload: dict[str, str | int | float | None] = {
        dut_key: boot_info.get(log_key)
        for log_key, dut_key in _BOOT_INFO_TO_DUT_INFO.items()
    }
    payload.update(
        {
            "cm5_ram_gb": variant_info.get("ram_gb"),
            "cm5_emmc_gb": variant_info.get("emmc_gb"),
            "cm5_wireless": variant_info.get("wireless"),
            "cm5_wireless_confidence": variant_info.get("wireless_confidence"),
            "cm5_part_number_source": variant_info.get("part_number_source"),
            "cm5_part_number_confidence": variant_info.get("part_number_confidence"),
        }
    )
    return payload


def set_dut_metadata_from_boot_info(
    boot_info: Mapping[str, str],
    variant_info: Mapping[str, Any],
) -> None:
    global _SERIAL_NUMBER_SET, _DUT_REVISION_SET, _DUT_PART_NUMBER_SET
    import hardpy

    serial = boot_info.get("SERIAL")
    if serial and not _SERIAL_NUMBER_SET:
        hardpy.set_dut_serial_number(serial)
        _SERIAL_NUMBER_SET = True

    boardrev = boot_info.get("BOARDREV")
    if boardrev and not _DUT_REVISION_SET:
        hardpy.set_dut_revision(boardrev)
        _DUT_REVISION_SET = True

    part_number = variant_info.get("part_number")
    if isinstance(part_number, str) and part_number and not _DUT_PART_NUMBER_SET:
        hardpy.set_dut_part_number(part_number)
        _DUT_PART_NUMBER_SET = True

    hardpy.set_dut_info(build_dut_info_payload(boot_info, variant_info))
