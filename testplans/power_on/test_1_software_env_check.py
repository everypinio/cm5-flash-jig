from __future__ import annotations

import pytest

from tests.env import settings
from tests.lib.hardpy_helpers.messages import (
    fail_with_operator_message,
    set_message,
)
from tests.lib.hardpy_helpers.reports import set_measurement
from tests.utils import (
    image_path,
    image_suffix,
    require_tool,
    required_decompressor,
)

HOST_SOFTWARE_TOOLS = ("lsblk", "rpiboot", "dd", "sync")
SUPPORTED_IMAGE_SUFFIXES = (".img", ".img.xz", ".img.gz")

pytestmark = [
    pytest.mark.module_name("1. Software Environment Check"),
    pytest.mark.critical,
]

@pytest.mark.case_name("1.1. Verify flash image")
def test_verify_flash_image(request: pytest.FixtureRequest) -> None:
    set_message(request, "Checking image file", "Image checks")

    image = image_path()
    set_measurement(request, "image path", str(image))
    if not image.exists():
        fail_with_operator_message(
            request,
            f"Image file does not exist: {image}. Set CM_FLASHER_IMAGE or copy the image file.",
        )
    if not image.is_file():
        fail_with_operator_message(request, f"Image path is not a file: {image}")

    suffix = image_suffix(image)
    set_measurement(request, "image suffix", suffix)
    if suffix not in SUPPORTED_IMAGE_SUFFIXES:
        fail_with_operator_message(
            request,
            f"Unsupported image extension: {image}. Expected .img, .img.xz, or .img.gz",
        )

    try:
        with image.open("rb"):
            pass
    except OSError as exc:
        fail_with_operator_message(
            request, f"Image file is not readable: {image}: {exc}"
        )
    set_measurement(request, "image readable", "yes")


@pytest.mark.case_name("1.2. Verify host tools")
def test_verify_host_tools(request: pytest.FixtureRequest) -> None:
    set_message(request, "Checking host software dependencies", "Tool checks")

    for tool in HOST_SOFTWARE_TOOLS:
        if tool == "rpiboot" and settings.MOCK_FLASHING:
            continue
        try:
            require_tool(request, tool)
        except RuntimeError as e:
            fail_with_operator_message(request, str(e), tool)

    image = image_path()
    decompressor = required_decompressor(image)
    if decompressor is not None:
        require_tool(request, decompressor)
        set_measurement(request, "image decompressor", decompressor)
    else:
        set_measurement(request, "image decompressor", "not required")
