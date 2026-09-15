from typing import Protocol


class PowerBlockDriverInterface(Protocol):
    """Protocol defining the required methods for a Power Block driver."""

    @property
    def is_connected(self) -> bool:
        """Return True when instrument session is open."""
        ...

    def connect(self) -> None:
        """Open session to Power Block source."""
        ...

    def disconnect(self) -> None:
        """Close session."""
        ...

    def get_uid(self) -> str:
        """Return instrument identity string."""
        ...

    def query_raw(self, command: str) -> str:
        """Return raw SCPI query response for diagnostics."""
        ...

    def write_raw(self, command: str) -> None:
        """Send a raw SCPI command for diagnostics or device-specific setup."""
        ...

    def set_supply(self, channel: int, state: str) -> None:
        """Enable or disable channel output (expected state: ON/OFF)."""
        ...

    def select_channel(self, channel: int) -> None:
        """Select output channel when the instrument supports channels."""
        ...

    def set_voltage(self, channel: int, value: float) -> None:
        """Set voltage setpoint in volts."""
        ...

    def set_current(self, channel: int, value: float) -> None:
        """Set current limit in amps."""
        ...

    def get_voltage_setpoint(self, channel: int = 0) -> float:
        """Read configured voltage setpoint in volts."""
        ...

    def get_current_setpoint(self, channel: int = 0) -> float:
        """Read configured current limit in amps."""
        ...

    def get_voltage(self, channel: int = 0) -> float:
        """Read measured output voltage in volts."""
        ...

    def get_current(self, channel: int = 0) -> float:
        """Read measured output current in amps."""
        ...
