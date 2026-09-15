from pathlib import Path
from typing import Annotated, Any

from pydantic import BeforeValidator


def _parse_flexible_int(v: Any) -> int:
    if isinstance(v, str):
        # int(v, 0) automatically detects 0x for hex
        return int(v, 0)
    return int(v)


def _parse_validate_dev(v: Any) -> Path:
    path = v if isinstance(v, Path) else Path(v)
    if not path.is_absolute() or not path.match("/dev/*"):
        raise ValueError("The device path must be an absolute file under /dev/")
    return path


FlexibleInt = Annotated[int, BeforeValidator(_parse_flexible_int)]
DevPath = Annotated[Path, BeforeValidator(_parse_validate_dev)]
