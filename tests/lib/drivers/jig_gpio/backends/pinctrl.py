import shutil
import subprocess

from .exceptions import GPIOBackendUnavailable


class PinctrlBackend:
    name = "pinctrl"

    def __init__(self) -> None:
        self._command = shutil.which("pinctrl")
        if not self._command:
            raise GPIOBackendUnavailable("pinctrl command is not available")

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
        if " hi" in text or "|hi" in text or "level=1" in text:
            return True
        if " lo" in text or "|lo" in text or "level=0" in text:
            return False
        raise RuntimeError(
            f"Could not parse pinctrl level for GPIO{pin}: {result.stdout.strip()}"
        )

    def write(self, pin: int, value: bool) -> None:
        self._run("set", str(pin), "op", "dh" if value else "dl")

    def close(self) -> None:
        return
