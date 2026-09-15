"""Short, fail-safe resistive load test for the onboard DUT supply."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gpiozero import DigitalInputDevice, DigitalOutputDevice

from tests.lib.drivers.ina229 import INA229


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resistance-ohms", type=float, required=True)
    parser.add_argument("--duration-s", type=float, default=5.0)
    parser.add_argument("--interval-s", type=float, default=0.5)
    parser.add_argument("--settle-s", type=float, default=0.2)
    parser.add_argument("--current-limit-a", type=float, default=1.0)
    parser.add_argument("--nominal-voltage-v", type=float, default=5.0)
    parser.add_argument("--enable-gpio", type=int, default=20)
    parser.add_argument("--alert-gpio", type=int, default=21)
    parser.add_argument("--spi-bus", type=int, default=0)
    parser.add_argument("--spi-device", type=int, default=1)
    parser.add_argument("--shunt-ohms", type=float, default=0.01)
    parser.add_argument(
        "--enable-output",
        action="store_true",
        help="Required acknowledgement that the load is connected safely",
    )
    parser.add_argument(
        "--expect-trip",
        action="store_true",
        help="Wait for the configured current threshold to trip instead of rejecting it",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.enable_output:
        raise SystemExit("Refusing to energize DUT power without --enable-output")
    if args.resistance_ohms <= 0:
        raise SystemExit("Load resistance must be positive")
    if args.duration_s <= 0 or args.interval_s <= 0 or args.settle_s < 0:
        raise SystemExit("Duration and interval must be positive; settle may be zero")

    expected_current_a = args.nominal_voltage_v / args.resistance_ohms
    expected_power_w = args.nominal_voltage_v * expected_current_a
    if expected_current_a >= args.current_limit_a and not args.expect_trip:
        raise SystemExit(
            f"Expected {expected_current_a:.3f} A is not below the configured "
            f"{args.current_limit_a:.3f} A trip threshold"
        )
    if args.expect_trip and expected_current_a <= args.current_limit_a:
        raise SystemExit(
            f"Expected {expected_current_a:.3f} A must exceed the configured "
            f"{args.current_limit_a:.3f} A threshold for a trip test"
        )

    output = DigitalOutputDevice(
        args.enable_gpio, active_high=True, initial_value=False
    )
    alert = DigitalInputDevice(
        args.alert_gpio, pull_up=None, active_state=True
    )
    monitor = INA229(
        bus=args.spi_bus,
        device=args.spi_device,
        shunt_ohms=args.shunt_ohms,
        max_current_a=3.0,
    )

    samples: list[tuple[float, float, float]] = []
    diagnostics: dict[str, bool | int] = {}
    trip_detected = False
    trip_elapsed_s: float | None = None
    started = time.monotonic()
    try:
        output.off()
        monitor.connect()
        monitor.configure(current_limit_a=args.current_limit_a)

        # Clear a previous latched event only while OUT_EN is low.
        diagnostics = monitor.read_diagnostics()
        time.sleep(0.05)
        if not bool(alert.value):
            raise RuntimeError(
                f"INA_ALERT is already active with output disabled: {diagnostics}"
            )

        print(f"identity={monitor.identify()}")
        print(f"expected_current_a={expected_current_a:.6f}")
        print(f"expected_power_w={expected_power_w:.6f}")
        print(f"current_trip_a={args.current_limit_a:.6f}")
        print("elapsed_s,voltage_v,current_a,resistance_ohms,power_w")

        output.on()
        time.sleep(args.settle_s)
        started = time.monotonic()
        while True:
            elapsed = time.monotonic() - started
            if not bool(alert.value):
                output.off()
                trip_detected = True
                trip_elapsed_s = elapsed
                print(f"trip_detected_at_s={elapsed:.6f}", flush=True)
                break

            voltage_v = monitor.read_bus_voltage()
            current_a = monitor.read_current()
            resistance_ohms = (
                voltage_v / current_a if abs(current_a) > 1e-9 else float("inf")
            )
            power_w = voltage_v * current_a
            samples.append((voltage_v, current_a, power_w))
            print(
                f"{elapsed:.3f},{voltage_v:.6f},{current_a:.6f},"
                f"{resistance_ohms:.6f},{power_w:.6f}",
                flush=True,
            )
            if elapsed >= args.duration_s:
                break
            time.sleep(min(args.interval_s, args.duration_s - elapsed))
    finally:
        output.off()
        time.sleep(0.05)
        if monitor.is_connected:
            diagnostics = monitor.read_diagnostics()
            monitor.close()
        alert.close()
        output.close()
        # gpiozero releases the line as an input on close. Keep OUT_EN driven
        # low after this standalone process exits; the board currently has no
        # external pull-down on this net.
        subprocess.run(
            ["pinctrl", "set", str(args.enable_gpio), "op", "dl"],
            check=True,
        )
        print(f"output=OFF diagnostics={diagnostics}", flush=True)

    if samples:
        count = len(samples)
        average_voltage = sum(item[0] for item in samples) / count
        average_current = sum(item[1] for item in samples) / count
        average_power = sum(item[2] for item in samples) / count
        print(f"average_voltage_v={average_voltage:.6f}")
        print(f"average_current_a={average_current:.6f}")
        print(f"average_power_w={average_power:.6f}")
        print(f"effective_resistance_ohms={average_voltage / average_current:.6f}")
    if args.expect_trip:
        print(f"trip={'DETECTED' if trip_detected else 'NOT_DETECTED'}")
        if trip_elapsed_s is not None:
            print(f"trip_elapsed_s={trip_elapsed_s:.6f}")
        if not trip_detected or not bool(diagnostics.get("shunt_over_limit")):
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
