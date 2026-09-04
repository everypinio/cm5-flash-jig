from pathlib import Path

import hardpy
import pytest

from tests.lib.hardpy_helpers.utils import _hardpy_enabled


def set_message(request: pytest.FixtureRequest, msg: str, title: str) -> None:
    if _hardpy_enabled(request):
        hardpy.set_message(msg, msg_key=title)


def fail_with_operator_message(
    request: pytest.FixtureRequest,
    message: str,
    title: str = "Check stand software",
) -> None:
    set_message(request, message, title)
    pytest.fail(message)


def set_operator_message(
    request: pytest.FixtureRequest,
    msg: str,
    title: str,
    *,
    image_path: Path | None = None,
) -> None:
    if _hardpy_enabled(request):
        image = None
        if image_path is not None:
            try:
                image = hardpy.ImageComponent(str(image_path), width=100)
            except Exception as exc:
                set_message(
                    request, f"Operator image unavailable: {image_path}: {exc}", title
                )
        hardpy.set_operator_message(msg, title=title, block=False, image=image)


def clear_operator_message(request: pytest.FixtureRequest) -> None:
    if _hardpy_enabled(request):
        hardpy.clear_operator_message()
