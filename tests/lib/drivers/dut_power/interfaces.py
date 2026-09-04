from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DutPowerCapabilities:
    programmable_voltage: bool
    programmable_current_limit: bool
    hardware_overcurrent_trip: bool


class DutPowerControllerInterface(Protocol):
    backend_name: str
    capabilities: DutPowerCapabilities

    def connect(self) -> None: ...

    def disconnect(self) -> None: ...

    def identity(self) -> str: ...

    def prepare(self, *, voltage_v: float, current_limit_a: float) -> None: ...

    def enable(self) -> None: ...

    def disable(self) -> None: ...

    def is_enabled(self) -> bool: ...

    def read_voltage(self) -> float: ...

    def read_current(self) -> float: ...

    def has_fault(self) -> bool: ...

    def diagnostics(self) -> dict[str, str | int | float | bool]: ...
