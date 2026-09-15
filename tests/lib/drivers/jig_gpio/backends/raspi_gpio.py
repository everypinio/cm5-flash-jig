import shutil
import subprocess

from .exceptions import GPIOBackendUnavailable


class RaspiGpioBackend:
    name = "raspi-gpio"

    def __init__(self) -> None:
        self._command = shutil.which("raspi-gpio")
        if not self._command:
            raise GPIOBackendUnavailable("raspi-gpio command is not available")

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        if not self._command:
            raise GPIOBackendUnavailable()
        return subprocess.run(
            [self._command, *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

    def setup_input(self, pin: int, *, pull: str | None) -> None:
        args = ["set", str(pin), "ip"]
        if pull == "up":
            args.append("pu")
        elif pull == "down":
            args.append("pd")
        elif pull is None:
            args.append("pn")
        self._run(*args)

    def setup_output(self, pin: int, *, initial: bool) -> None:
        self._run("set", str(pin), "op", "dh" if initial else "dl")

    def read(self, pin: int) -> bool:
        result = self._run("get", str(pin))
        text = result.stdout.lower()
        if "level=1" in text:
            return True
        if "level=0" in text:
            return False
        raise RuntimeError(
            f"Could not parse raspi-gpio level for GPIO{pin}: {result.stdout.strip()}"
        )

    def write(self, pin: int, value: bool) -> None:
        self._run("set", str(pin), "op", "dh" if value else "dl")

    def close(self) -> None:
        return
