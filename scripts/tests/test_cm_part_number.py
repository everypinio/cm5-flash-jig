import sys
import unittest
from unittest.mock import Mock, patch

from tests.lib.utils.cm5_boot_info import infer_cm_part_number, parse_boot_info
from tests.lib.hardpy_helpers import cm5_hardpy_dut_info as metadata


def boot_log(model):
    return (
        f"Machine model: {model}\n"
        "Memory: 3800000K/4194304K available\n"
        "mmcblk0: mmc0:0001 AJTD4R 14.6 GiB\n"
        "mmc1: new high speed SDIO card at address 0001\n"
    )


class PartNumberTests(unittest.TestCase):
    def test_cm4_part_number(self):
        result = infer_cm_part_number(boot_log("Raspberry Pi Compute Module 4 Rev 1.1"))
        self.assertEqual(result["part_number"], "CM4104016")
        self.assertEqual(result["module_family"], "CM4")
        self.assertEqual(result["part_number_confidence"], "probable")

    def test_cm5_part_number(self):
        result = infer_cm_part_number(boot_log("Raspberry Pi Compute Module 5 Rev 1.0"))
        self.assertEqual(result["part_number"], "CM5104016")

    def test_unknown_or_different_models_do_not_become_cm5(self):
        for model in ("", "Raspberry Pi 4 Model B Rev 1.1", "Raspberry Pi Compute Module 4S Rev 1.0"):
            with self.subTest(model=model):
                self.assertIsNone(infer_cm_part_number(boot_log(model))["part_number"])

    def test_incomplete_log_has_no_part_number(self):
        result = infer_cm_part_number("Machine model: Raspberry Pi Compute Module 4 Rev 1.1\n")
        self.assertIsNone(result["part_number"])

    def test_cm4_part_number_is_written_to_hardpy_once(self):
        log = boot_log("Raspberry Pi Compute Module 4 Rev 1.1")
        hardpy = Mock()
        with patch.dict(sys.modules, {"hardpy": hardpy}), \
             patch.object(metadata, "_DUT_PART_NUMBER_SET", False):
            for _ in range(2):
                metadata.set_dut_metadata_from_boot_info(parse_boot_info(log), infer_cm_part_number(log))
        hardpy.set_dut_part_number.assert_called_once_with("CM4104016")


if __name__ == "__main__":
    unittest.main()
