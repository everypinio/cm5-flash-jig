from typing import Optional


class MockPowerBlockDriver:
    """Mock Power Block driver for off-device testing."""

    def __init__(
        self,
        resource_name: Optional[str] = None,
        vid: str = "0xCAFF",
        pid: str = "0x4000",
        timeout_ms: int = 5000,
    ) -> None:
        self.resource_name = resource_name
        self.vid = vid
        self.pid = pid
        self.timeout_ms = timeout_ms

        self._is_connected = False

        # State tracking per channel
        self._supply_state: dict[int, str] = {}
        self._voltage_setpoint: dict[int, float] = {}
        self._current_setpoint: dict[int, float] = {}

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    def connect(self) -> None:
        if self._is_connected:
            return
        self._is_connected = True

    def disconnect(self) -> None:
        self._is_connected = False

    def get_uid(self) -> str:
        if not self._is_connected:
            raise RuntimeError("Power Block is not connected")
        return "MOCK_POWER_BLOCK_DRIVER"

    def query_raw(self, command: str) -> str:
        if not self._is_connected:
            raise RuntimeError("Power Block is not connected")
        return "MOCK_RESPONSE"

    def write_raw(self, command: str) -> None:
        if not self._is_connected:
            raise RuntimeError("Power Block is not connected")

    def set_supply(self, channel: int, state: str) -> None:
        if not self._is_connected:
            raise RuntimeError("Power Block is not connected")
        self.select_channel(channel)
        state_up = state.strip().upper()
        if state_up not in {"ON", "OFF"}:
            raise ValueError("state must be 'ON' or 'OFF'")
        self._supply_state[channel] = state_up

    def select_channel(self, channel: int) -> None:
        pass

    def set_voltage(self, channel: int, value: float) -> None:
        if not self._is_connected:
            raise RuntimeError("Power Block is not connected")
        self.select_channel(channel)
        self._voltage_setpoint[channel] = value

    def set_current(self, channel: int, value: float) -> None:
        if not self._is_connected:
            raise RuntimeError("Power Block is not connected")
        self.select_channel(channel)
        self._current_setpoint[channel] = value

    def get_voltage_setpoint(self, channel: int = 0) -> float:
        if not self._is_connected:
            raise RuntimeError("Power Block is not connected")
        self.select_channel(channel)
        return self._voltage_setpoint.get(channel, 0.0)

    def get_current_setpoint(self, channel: int = 0) -> float:
        if not self._is_connected:
            raise RuntimeError("Power Block is not connected")
        self.select_channel(channel)
        return self._current_setpoint.get(channel, 0.0)

    def get_voltage(self, channel: int = 0) -> float:
        """Returns the setpoint if ON, 0.0 if OFF."""
        if not self._is_connected:
            raise RuntimeError("Power Block is not connected")
        self.select_channel(channel)
        if self._supply_state.get(channel, "OFF") == "ON":
            return self.get_voltage_setpoint(channel)
        return 0.0

    def get_current(self, channel: int = 0) -> float:
        """Returns a nominal mock current if ON, 0.0 if OFF."""
        if not self._is_connected:
            raise RuntimeError("Power Block is not connected")
        self.select_channel(channel)
        if self._supply_state.get(channel, "OFF") == "ON":
            # Just return half of the setpoint as a fake active current
            return self.get_current_setpoint(channel) / 2.0
        return 0.0


if __name__ == "__main__":
    pb = MockPowerBlockDriver()
    pb.connect()
    print(pb.get_uid())
    pb.set_voltage(1, 5)
    pb.set_current(1, 2)
    pb.set_supply(1, "ON")
    print(f"curr:{pb.get_current()}")
    print(f"volt:{pb.get_voltage()}")
    pb.disconnect()
