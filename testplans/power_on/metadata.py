"""HardPy identity metadata for the CM5 flasher power-on self-test."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any, Iterable

MACHINE_ID_PATHS = (
    Path("/etc/machine-id"),
    Path("/var/lib/dbus/machine-id"),
)


def resolve_station_serial_number(
    configured_serial_number: str | None,
    *,
    machine_id_paths: Iterable[Path] = MACHINE_ID_PATHS,
) -> str:
    """Return the configured station serial or a stable host identifier."""

    if configured_serial_number and configured_serial_number.strip():
        return configured_serial_number.strip()

    for path in machine_id_paths:
        try:
            machine_id = path.read_text(encoding="ascii").strip()
        except OSError:
            continue
        if machine_id:
            return machine_id

    return socket.gethostname()


def set_power_on_hardpy_metadata(
    hardpy_module: Any,
    settings: Any,
    *,
    machine_id_paths: Iterable[Path] = MACHINE_ID_PATHS,
) -> None:
    """Populate all standard identity fields for a power-on report."""

    serial_number = resolve_station_serial_number(
        settings.POWER_ON_HARDPY_DUT_SERIAL_NUMBER,
        machine_id_paths=machine_id_paths,
    )

    hardpy_module.set_user_name(settings.POWER_ON_HARDPY_USER_NAME)
    hardpy_module.set_dut_name(settings.POWER_ON_HARDPY_DUT_NAME)
    hardpy_module.set_dut_type(settings.POWER_ON_HARDPY_DUT_TYPE)
    hardpy_module.set_dut_part_number(settings.POWER_ON_HARDPY_DUT_PART_NUMBER)
    hardpy_module.set_dut_serial_number(serial_number)
    hardpy_module.set_batch_serial_number(
        settings.POWER_ON_HARDPY_BATCH_SERIAL_NUMBER
    )
    hardpy_module.set_stand_name(settings.POWER_ON_HARDPY_STAND_NAME)
