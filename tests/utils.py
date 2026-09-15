import shutil
from pathlib import Path

import pytest

from tests.env import settings
from tests.lib.hardpy_helpers.reports import set_measurement


def require_tool(request: pytest.FixtureRequest, tool: str) -> str:
    tool_path = shutil.which(tool)
    set_measurement(request, f"tool {tool}", tool_path or "missing")

    if not tool_path:
        raise RuntimeError("Required host tool is missing")
    return tool_path


def require_linux_device(device: Path) -> Path:
    if not Path(device).exists():
        pytest.fail(f"Required Linux device is missing: {device})")
    return device


def image_path() -> Path:
    return Path(settings.CM_FLASHER_IMAGE).expanduser()


def image_suffix(path: Path) -> str:
    suffixes = "".join(path.suffixes[-2:])
    if suffixes in {".img.xz", ".img.gz"}:
        return suffixes
    return path.suffix


def required_decompressor(path: Path) -> str | None:
    suffix = image_suffix(path)
    if suffix == ".img.xz":
        return "xz"
    if suffix == ".img.gz":
        return "gzip"
    return None
