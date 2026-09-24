import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tests import test_3_boot_verification as boot


class BootLogPersistenceTests(unittest.TestCase):
    def test_empty_log_is_saved_and_attached_during_capture_step(self):
        for name, value in (("UART_BOOT_LOG_3", None), ("UART_BOOT_LOG_PATH", None),
                            ("SAW_LOGIN", False), ("FATAL_MATCHES", [])):
            self.enterContext(patch.object(boot, name, value))
        self.enterContext(patch.object(boot.settings, "CM_FLASHER_ENABLE_POWER_WRITE", True))
        self.enterContext(patch.object(boot, "open_uart", return_value=-1))
        self.enterContext(patch.object(boot, "wait_for_dut_present", return_value=True))
        self.enterContext(patch.object(boot, "read_uart_boot_log", return_value=("", False, [])))
        for name in ("set_message", "set_measurement", "set_numeric_measurement"):
            self.enterContext(patch.object(boot, name))
        save = self.enterContext(patch.object(boot, "write_boot_log", return_value=Path("capture.log")))
        artifact = self.enterContext(patch.object(boot, "_set_boot_log_artifact"))
        boot.test_execute_normal_boot(Mock(), Mock(), Mock(), Mock())
        save.assert_called_once_with("")
        self.assertEqual(boot.UART_BOOT_LOG_PATH, Path("capture.log"))
        self.assertEqual(artifact.call_args.kwargs["log_text"], "")
        self.assertFalse(artifact.call_args.kwargs["saw_login"])


if __name__ == "__main__":
    unittest.main()
