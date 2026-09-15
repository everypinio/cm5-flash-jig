#!/usr/bin/env bash

setup_raspi_config() {
    local uart_device
    local uart_tty

    echo "Configuring Raspberry Pi hardware (I2C, SPI, Serial, Bluetooth)..."
    if command -v raspi-config >/dev/null 2>&1; then
        echo " - Enabling I2C..."
        sudo raspi-config nonint do_i2c 0

        echo " - Enabling SPI..."
        sudo raspi-config nonint do_spi 0

        echo " - Disabling the login console on the DUT UART..."
        sudo raspi-config nonint do_serial_cons 1

        echo " - Enabling Serial Hardware..."
        sudo raspi-config nonint do_serial_hw 0

        uart_device="$(readlink -f /dev/serial0 2>/dev/null || true)"
        if [ -n "$uart_device" ]; then
            uart_tty="$(basename "$uart_device")"
            echo " - Reserving /dev/serial0 ($uart_tty) for DUT logs..."
            sudo systemctl mask --now "serial-getty@${uart_tty}.service"
        fi

        BOOT_CONFIG="/boot/firmware/config.txt"
        if [ ! -f "$BOOT_CONFIG" ]; then
            BOOT_CONFIG="/boot/config.txt"
        fi
        
        if [ -f "$BOOT_CONFIG" ] && ! sudo grep -q '^dtoverlay=disable-bt$' "$BOOT_CONFIG"; then
            echo " - Disabling Bluetooth in $BOOT_CONFIG..."
            sudo sed -i '/^dtparam=i2c_arm=on$/a dtoverlay=disable-bt' "$BOOT_CONFIG"
        fi
        
        REBOOT_REQUIRED=1
    else
        echo "ERROR: raspi-config not found. Hardware cannot be configured. Stopping bootstrap." >&2
        exit 1
    fi
}
