from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

from testplans.power_on.metadata import (
    resolve_station_serial_number,
    set_power_on_hardpy_metadata,
)


class PowerOnMetadataTests(unittest.TestCase):
    def test_configured_serial_number_takes_precedence(self) -> None:
        serial_number = resolve_station_serial_number(
            "  station-42  ",
            machine_id_paths=(),
        )

        self.assertEqual(serial_number, "station-42")

    def test_machine_id_is_used_when_serial_number_is_not_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            machine_id_path = Path(temporary_directory) / "machine-id"
            machine_id_path.write_text("abc123\n", encoding="ascii")

            serial_number = resolve_station_serial_number(
                None,
                machine_id_paths=(machine_id_path,),
            )

        self.assertEqual(serial_number, "abc123")

    def test_all_standard_hardpy_identity_fields_are_set(self) -> None:
        hardpy_module = Mock()
        settings = SimpleNamespace(
            POWER_ON_HARDPY_USER_NAME="Operator",
            POWER_ON_HARDPY_DUT_NAME="CM5 flasher",
            POWER_ON_HARDPY_DUT_TYPE="Test jig",
            POWER_ON_HARDPY_DUT_PART_NUMBER="CM5-FLASHER",
            POWER_ON_HARDPY_DUT_SERIAL_NUMBER="station-42",
            POWER_ON_HARDPY_BATCH_SERIAL_NUMBER="POWER-ON-SELFTEST",
            POWER_ON_HARDPY_STAND_NAME="CM5 flasher",
        )

        set_power_on_hardpy_metadata(
            hardpy_module,
            settings,
            machine_id_paths=(),
        )

        self.assertEqual(
            hardpy_module.method_calls,
            [
                call.set_user_name("Operator"),
                call.set_dut_name("CM5 flasher"),
                call.set_dut_type("Test jig"),
                call.set_dut_part_number("CM5-FLASHER"),
                call.set_dut_serial_number("station-42"),
                call.set_batch_serial_number("POWER-ON-SELFTEST"),
                call.set_stand_name("CM5 flasher"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
