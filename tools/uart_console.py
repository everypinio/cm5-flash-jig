"""Enable PwrBlock 5 V / 3 A, then provide an interactive UART console.

Typical wiring for CM4/CM5 debug UART:
- DUT TX -> host RX
- DUT GND -> host GND

Run on the host Raspberry Pi, for example:
    python3 uart_console.py
    python3 uart_console.py --port /dev/serial0 --baud 115200
    python3 uart_console.py --no-pwrblock
    python3 uart_console.py --read-only
"""

from __future__ import annotations

import argparse
import glob
import os
import select
import signal
import sys
import termios
import time
from pathlib import Path


DEFAULT_PORTS = (
    "/dev/serial0",
    "/dev/ttyAMA0",
    "/dev/ttyAMA1",
    "/dev/ttyS0",
    "/dev/ttyUSB0",
    "/dev/ttyACM0",
)


class UartError(RuntimeError):
    pass


class PowerSetupError(RuntimeError):
    pass


def available_ports() -> list[str]:
    ports: list[str] = []
    for port in DEFAULT_PORTS:
        if Path(port).exists() and port not in ports:
            ports.append(port)
    for pattern in ("/dev/ttyUSB*", "/dev/ttyACM*", "/dev/ttyAMA*", "/dev/ttyS*"):
        for port in sorted(glob.glob(pattern)):
            if port not in ports:
                ports.append(port)
    return ports


def resolve_port(port: str | None) -> str:
    if port:
        return port
    ports = available_ports()
    if not ports:
        raise UartError(
            "No UART device found. Try --port /dev/serial0, /dev/ttyAMA0, "
            "/dev/ttyS0, /dev/ttyUSB0, or /dev/ttyACM0."
        )
    return ports[0]


def baud_constant(baud: int) -> int:
    name = f"B{baud}"
    value = getattr(termios, name, None)
    if value is None:
        raise UartError(f"Unsupported baud rate by this system: {baud}")
    return value


def configure_uart(
    fd: int,
    *,
    baud: int,
    data_bits: int,
    parity: str,
    stop_bits: int,
) -> None:
    attrs = termios.tcgetattr(fd)
    baud_flag = baud_constant(baud)

    if data_bits not in {5, 6, 7, 8}:
        raise UartError("--data-bits must be 5, 6, 7, or 8")
    if stop_bits not in {1, 2}:
        raise UartError("--stop-bits must be 1 or 2")

    data_bit_flags = {
        5: termios.CS5,
        6: termios.CS6,
        7: termios.CS7,
        8: termios.CS8,
    }

    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = termios.CLOCAL | termios.CREAD | data_bit_flags[data_bits]
    attrs[3] = 0
    attrs[4] = baud_flag
    attrs[5] = baud_flag
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 0

    if parity == "even":
        attrs[2] |= termios.PARENB
    elif parity == "odd":
        attrs[2] |= termios.PARENB | termios.PARODD
    elif parity != "none":
        raise UartError("--parity must be none, even, or odd")

    if stop_bits == 2:
        attrs[2] |= termios.CSTOPB

    crtscts = getattr(termios, "CRTSCTS", 0)
    if crtscts:
        attrs[2] &= ~crtscts

    termios.tcsetattr(fd, termios.TCSANOW, attrs)


def print_hex(data: bytes, *, timestamp: bool) -> None:
    prefix = f"{time.strftime('%Y-%m-%d %H:%M:%S')} " if timestamp else ""
    print(prefix + " ".join(f"{byte:02X}" for byte in data), flush=True)


def print_text(data: bytes) -> None:
    text = data.decode("utf-8", errors="replace")
    print(text, end="", flush=True)


def configure_stdin() -> list[object] | None:
    if not sys.stdin.isatty():
        return None

    fd = sys.stdin.fileno()
    old_attrs = termios.tcgetattr(fd)
    new_attrs = list(old_attrs)
    new_attrs[6] = list(old_attrs[6])
    new_attrs[3] &= ~(termios.ICANON | termios.ECHO)
    new_attrs[6][termios.VMIN] = 0
    new_attrs[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, new_attrs)
    return old_attrs


def restore_stdin(old_attrs: list[object] | None) -> None:
    if old_attrs is not None:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, old_attrs)


def translate_stdin(data: bytes, enter_mode: str) -> bytes:
    if enter_mode == "raw":
        return data

    enter_bytes = {
        "cr": b"\r",
        "lf": b"\n",
        "crlf": b"\r\n",
    }[enter_mode]

    output = bytearray()
    for byte in data:
        if byte in {10, 13}:
            output.extend(enter_bytes)
        else:
            output.append(byte)
    return bytes(output)


def output_enabled(response: str) -> bool:
    text = response.replace("\x00", "").strip().upper()
    return text in {"1", "ON", "TRUE", "ENABLED"}


def query_if_supported(driver: object, command: str) -> str:
    try:
        return str(driver.query_raw(command)).replace("\x00", "").strip()
    except Exception as exc:
        return f"<error: {exc}>"


def clear_pwrblock_errors(driver: object) -> None:
    try:
        driver.write_raw("*CLS")
    except Exception:
        pass


def pwrblock_errors(driver: object) -> str:
    return query_if_supported(driver, "SYST:ERR?")


def configure_power_block(args: argparse.Namespace) -> None:
    if args.no_pwrblock:
        print("Skipping PwrBlock setup (--no-pwrblock).", file=sys.stderr)
        return

    try:
        from lib.power_block_driver import PowerBlockDriver
    except ImportError as exc:
        raise PowerSetupError(f"Could not import PowerBlock driver: {exc}") from exc

    driver = PowerBlockDriver(
        resource_name=args.pwrblock_resource,
        timeout_ms=args.pwrblock_timeout_ms,
    )

    try:
        driver.connect()
        try:
            print(f"PwrBlock: {driver.get_uid()}", file=sys.stderr)
        except Exception as exc:
            print(f"PwrBlock identity read failed: {exc}", file=sys.stderr)

        clear_pwrblock_errors(driver)
        driver.set_supply(args.pwrblock_channel, "OFF")
        time.sleep(0.1)

        voltage = 0.0
        current = 0.0
        output = ""
        errors: list[str] = []

        for attempt in range(1, args.pwrblock_attempts + 1):
            driver.set_voltage(args.pwrblock_channel, args.pwrblock_voltage)
            driver.set_current(args.pwrblock_channel, args.pwrblock_current)
            driver.set_supply(args.pwrblock_channel, "ON")
            time.sleep(args.pwrblock_settle_s)

            voltage = driver.get_voltage_setpoint(args.pwrblock_channel)
            current = driver.get_current_setpoint(args.pwrblock_channel)
            driver.select_channel(args.pwrblock_channel)
            output = driver.query_raw("OUTP?")

            errors = []
            if abs(voltage - args.pwrblock_voltage) > args.pwrblock_voltage_tolerance:
                errors.append(
                    f"voltage setpoint is {voltage:.3f} V, expected {args.pwrblock_voltage:.3f} V"
                )
            if abs(current - args.pwrblock_current) > args.pwrblock_current_tolerance:
                errors.append(
                    f"current limit is {current:.3f} A, expected {args.pwrblock_current:.3f} A"
                )
            if not output_enabled(output):
                errors.append(f"output is not ON, OUTP? returned {output!r}")

            if not errors:
                break

        if errors:
            scpi_error = pwrblock_errors(driver)
            raise PowerSetupError("; ".join(errors) + f"; SYST:ERR? => {scpi_error}")

        print(
            f"PwrBlock OK: {voltage:.3f} V, {current:.3f} A, output ON.",
            file=sys.stderr,
        )
    except Exception as exc:
        if isinstance(exc, PowerSetupError):
            raise
        raise PowerSetupError(f"Could not configure PwrBlock: {exc}") from exc
    finally:
        driver.disconnect()


def monitor_uart(args: argparse.Namespace) -> int:
    configure_power_block(args)

    port = resolve_port(args.port)
    fd: int | None = None
    old_stdin_attrs: list[object] | None = None
    stop = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    try:
        fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        configure_uart(
            fd,
            baud=args.baud,
            data_bits=args.data_bits,
            parity=args.parity,
            stop_bits=args.stop_bits,
        )

        input_enabled = not args.read_only and sys.stdin.isatty()
        if input_enabled:
            old_stdin_attrs = configure_stdin()
            print(
                f"Connected to {port} at {args.baud} baud. Type to send, Ctrl+C to stop.",
                file=sys.stderr,
            )
        else:
            if not args.read_only:
                print("stdin is not a terminal; UART transmit is disabled.", file=sys.stderr)
            print(f"Listening on {port} at {args.baud} baud. Press Ctrl+C to stop.", file=sys.stderr)

        while not stop:
            read_fds = [fd]
            if input_enabled:
                read_fds.append(sys.stdin.fileno())

            readable, _, _ = select.select(read_fds, [], [], 0.5)
            if not readable:
                continue

            if fd in readable:
                try:
                    data = os.read(fd, args.chunk_size)
                except BlockingIOError:
                    data = b""
                if data:
                    if args.hex:
                        print_hex(data, timestamp=args.timestamp)
                    else:
                        print_text(data)

            if input_enabled and sys.stdin.fileno() in readable:
                try:
                    typed = os.read(sys.stdin.fileno(), args.chunk_size)
                except BlockingIOError:
                    typed = b""
                if typed:
                    os.write(fd, translate_stdin(typed, args.enter))
    except PermissionError as exc:
        raise UartError(
            f"Permission denied for {port}. Try running with sudo or add the user "
            "to the dialout group."
        ) from exc
    except OSError as exc:
        raise UartError(f"Could not open/read {port}: {exc}") from exc
    finally:
        restore_stdin(old_stdin_attrs)
        if fd is not None:
            os.close(fd)

    print("\nUART monitor stopped.", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive Raspberry Pi UART console.")
    parser.add_argument("--port", help="UART device, for example /dev/serial0 or /dev/ttyUSB0.")
    parser.add_argument("--baud", type=int, default=115200, help="UART speed. Default: 115200.")
    parser.add_argument("--data-bits", type=int, default=8, help="Data bits. Default: 8.")
    parser.add_argument(
        "--parity",
        choices=("none", "even", "odd"),
        default="none",
        help="Parity mode. Default: none.",
    )
    parser.add_argument("--stop-bits", type=int, default=1, help="Stop bits. Default: 1.")
    parser.add_argument("--chunk-size", type=int, default=4096, help="Read chunk size in bytes.")
    parser.add_argument("--hex", action="store_true", help="Print bytes as hexadecimal instead of text.")
    parser.add_argument("--timestamp", action="store_true", help="Add timestamps in --hex mode.")
    parser.add_argument("--read-only", action="store_true", help="Only print UART data; do not send keyboard input.")
    parser.add_argument(
        "--enter",
        choices=("cr", "lf", "crlf", "raw"),
        default="cr",
        help="Bytes sent when Enter is pressed. Default: cr.",
    )
    parser.add_argument("--list", action="store_true", help="List detected UART-like devices and exit.")
    parser.add_argument(
        "--no-pwrblock",
        action="store_true",
        help="Skip PwrBlock setup before opening UART.",
    )
    parser.add_argument("--pwrblock-resource", help="VISA resource or /dev/usbtmcN path for PwrBlock.")
    parser.add_argument("--pwrblock-channel", type=int, default=1, help="PwrBlock channel. Default: 1.")
    parser.add_argument("--pwrblock-voltage", type=float, default=5.0, help="PwrBlock voltage in volts.")
    parser.add_argument("--pwrblock-current", type=float, default=3.0, help="PwrBlock current limit in amps.")
    parser.add_argument(
        "--pwrblock-attempts",
        type=int,
        default=2,
        help="How many times to apply and verify PwrBlock settings.",
    )
    parser.add_argument(
        "--pwrblock-timeout-ms",
        type=int,
        default=5000,
        help="PwrBlock communication timeout in milliseconds.",
    )
    parser.add_argument(
        "--pwrblock-settle-s",
        type=float,
        default=0.25,
        help="Delay after enabling PwrBlock output before verification.",
    )
    parser.add_argument(
        "--pwrblock-voltage-tolerance",
        type=float,
        default=0.05,
        help="Allowed voltage setpoint error in volts.",
    )
    parser.add_argument(
        "--pwrblock-current-tolerance",
        type=float,
        default=0.05,
        help="Allowed current setpoint error in amps.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        ports = available_ports()
        if ports:
            print("\n".join(ports))
            return 0
        print("No UART-like devices found.")
        return 1

    try:
        return monitor_uart(args)
    except (PowerSetupError, UartError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
