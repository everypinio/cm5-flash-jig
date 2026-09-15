"""Parse Raspberry Pi CM5 boot logs into DUT metadata."""

from __future__ import annotations

import re
from typing import Any

DUT_INFO_FIELDS = (
    "MODEL",
    "SERIAL",
    "BOARDREV",
    "EMMC_CID",
    "EMMC model",
    "EMMC size GiB",
    "MAC",
    "IP address",
    "Hostname",
    "Linux version",
    "BOOTLOADER release VERSION",
    "BOOTLOADER release DATE",
    "BOOTLOADER release TIME",
    "BOOTSYS release VERSION",
    "BOOTSYS release DATE",
    "BOOTSYS release TIME",
    "RPIBOOT release VERSION",
    "RPIBOOT release DATE",
    "RPIBOOT release TIME",
    "BOOTMODE",
    "Boot mode",
    "MFG_VER",
    "EEPROM ID",
    "RP1_BOOT chip ID",
)

CM5_RAM_CODES = {
    1: "01",
    2: "02",
    4: "04",
    8: "08",
    16: "16",
}
CM5_EMMC_CODES = {
    0: "000",
    8: "008",
    16: "016",
    32: "032",
    64: "064",
    128: "128",
}
CM5_MARKETED_EMMC_GB = (0, 8, 16, 32, 64, 128)


def _extract_first(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, re.MULTILINE)
    if match is None:
        return None
    return match.group(1).strip()


def parse_boot_info(log_text: str) -> dict[str, str]:
    info: dict[str, str] = {}
    patterns = {
        "MODEL": r"Machine model:\s*(.+)",
        "SERIAL": r"\bserial\s+([0-9a-fA-F]+)\b",
        "BOARDREV": r"\bboardrev\s+([0-9a-fA-F]+)\b",
        "EMMC_CID": r"\bCID:\s*([0-9a-fA-F]+)",
        "EMMC model": r"\bmmcblk0:\s+mmc\d+:\d+\s+(\S+)\s+\d+(?:\.\d+)?\s+GiB",
        "EMMC size GiB": r"\bmmcblk0:\s+mmc\d+:\d+\s+\S+\s+(\d+(?:\.\d+)?)\s+GiB",
        "MAC": r"\bmacaddr=([0-9A-Fa-f:]{17})",
        "IP address": r"My IP address is\s*(.+)",
        "Hostname": r"Hostname set to <([^>]+)>",
        "Linux version": r"Linux version\s+(\S+)",
        "BOOTLOADER release VERSION": r"RPi:\s+BOOTLOADER release VERSION:([^\s]+)",
        "BOOTLOADER release DATE": r"RPi:\s+BOOTLOADER release VERSION:[^\s]+\s+DATE:\s*([^\s]+)",
        "BOOTLOADER release TIME": r"RPi:\s+BOOTLOADER release VERSION:[^\s]+\s+DATE:\s*[^\s]+\s+TIME:\s*([^\s]+)",
        "BOOTSYS release VERSION": r"RPi:\s+BOOTSYS release VERSION:([^\s]+)",
        "BOOTSYS release DATE": r"RPi:\s+BOOTSYS release VERSION:[^\s]+\s+DATE:\s*([^\s]+)",
        "BOOTSYS release TIME": r"RPi:\s+BOOTSYS release VERSION:[^\s]+\s+DATE:\s*[^\s]+\s+TIME:\s*([^\s]+)",
        "RPIBOOT release VERSION": r"RPi:\s+RPIBOOT release VERSION:([^\s]+)",
        "RPIBOOT release DATE": r"RPi:\s+RPIBOOT release VERSION:[^\s]+\s+DATE:\s*([^\s]+)",
        "RPIBOOT release TIME": r"RPi:\s+RPIBOOT release VERSION:[^\s]+\s+DATE:\s*[^\s]+\s+TIME:\s*([^\s]+)",
        "BOOTMODE": r"\bBOOTMODE:\s*([^\s]+)",
        "Boot mode": r"\bBoot mode:\s*([^\r\n]+)",
        "MFG_VER": r"\bMFG_VER:\s*([^\r\n]+)",
        "EEPROM ID": r"\bEEPROM ID:\s*([^\r\n]+)",
        "RP1_BOOT chip ID": r"\bRP1_BOOT chip ID:\s*([^\r\n]+)",
    }

    for name, pattern in patterns.items():
        value = _extract_first(pattern, log_text)
        if value:
            info[name] = value

    if "MAC" not in info:
        value = _extract_first(r"\beth0:.*\(([0-9A-Fa-f:]{17})\)", log_text)
        if value:
            info["MAC"] = value

    return info


def _nearest_option(value: float, options: tuple[int, ...]) -> int:
    return min(options, key=lambda option: abs(option - value))


def infer_ram_gb(log_text: str) -> int | None:
    value = _extract_first(r"total-size:\s*(\d+)\s*Gbit", log_text)
    if value:
        gbit = int(value)
        gb = gbit // 8
        if gb in CM5_RAM_CODES:
            return gb

    value = _extract_first(r"Memory:\s+\d+K/(\d+)K\s+available", log_text)
    if value:
        gib = int(value) / 1024 / 1024
        gb = _nearest_option(gib, tuple(CM5_RAM_CODES))
        if gb in CM5_RAM_CODES:
            return gb

    return None


def _gib_to_marketed_gb(gib: float) -> int:
    if gib <= 0.1:
        return 0

    def marketed_to_gib(gb: int) -> float:
        return gb * 1_000_000_000 / (1024**3)

    return min(
        CM5_MARKETED_EMMC_GB[1:],
        key=lambda gb: abs(marketed_to_gib(gb) - gib),
    )


def infer_emmc_gb(log_text: str) -> int | None:
    value = _extract_first(
        r"\bmmcblk0:\s+mmc\d+:[^\n]*?\s+(\d+(?:\.\d+)?)\s+GiB", log_text
    )
    if value:
        gb = _gib_to_marketed_gb(float(value))
        if gb in CM5_EMMC_CODES:
            return gb

    return None


def infer_wireless(log_text: str) -> tuple[bool | None, str]:
    if re.search(r"\b(brcmfmac|wlan0|hci0|Bluetooth)\b", log_text, re.IGNORECASE):
        return True, "confirmed"

    if re.search(r"\bmmc\d+:\s+new .*SDIO card", log_text, re.IGNORECASE):
        return True, "probable_sdio_card"

    return None, "unknown"


def infer_cm5_part_number(log_text: str) -> dict[str, Any]:
    ram_gb = infer_ram_gb(log_text)
    emmc_gb = infer_emmc_gb(log_text)
    wireless, wireless_confidence = infer_wireless(log_text)

    ram_code = CM5_RAM_CODES.get(ram_gb)
    emmc_code = CM5_EMMC_CODES.get(emmc_gb)
    wireless_code = None if wireless is None else ("1" if wireless else "0")
    part_number = None
    part_number_confidence = "incomplete"

    if wireless_code is not None and ram_code and emmc_code:
        part_number = f"CM5{wireless_code}{ram_code}{emmc_code}"
        part_number_confidence = (
            "probable" if wireless_confidence.startswith("probable") else "inferred"
        )

    return {
        "part_number": part_number,
        "part_number_source": "inferred_from_boot_log",
        "part_number_confidence": part_number_confidence,
        "wireless": wireless,
        "wireless_confidence": wireless_confidence,
        "wireless_code": wireless_code,
        "ram_gb": ram_gb,
        "ram_code": ram_code,
        "emmc_gb": emmc_gb,
        "emmc_code": emmc_code,
    }
