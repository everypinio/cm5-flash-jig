import shutil
import subprocess
import threading
from pathlib import Path


class RpibootRunner:
    def __init__(
        self,
        command: str,
        *,
        use_sudo: bool,
        boot_dir: Path | None,
    ) -> None:
        self.command = command
        self.use_sudo = use_sudo
        self.boot_dir = boot_dir
        self.process: subprocess.Popen[str] | None = None
        self.output: list[str] = []
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "RpibootRunner":
        self.process = subprocess.Popen(
            self._argv(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self._thread = threading.Thread(
            target=self._read_output, name="rpiboot-output", daemon=True
        )
        self._thread.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()

    def _argv(self) -> list[str]:
        if shutil.which(self.command) is None:
            raise RuntimeError(f"Required tool is missing: {self.command}")

        argv = [self.command]
        if self.boot_dir:
            argv.extend(["-d", str(self.boot_dir)])
        if self.use_sudo:
            if shutil.which("sudo") is None:
                raise RuntimeError("Required tool is missing: sudo")
            argv.insert(0, "sudo")
        return argv

    def _read_output(self) -> None:
        assert self.process is not None
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self.output.append(line)

    def poll(self) -> int | None:
        if self.process is None:
            return None
        return self.process.poll()

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def output_text(self) -> str:
        return "".join(self.output)
