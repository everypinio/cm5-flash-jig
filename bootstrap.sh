#!/usr/bin/env bash

set -eu

if [ "$EUID" -eq 0 ]; then
    echo "ERROR: This script must NOT be run as root or via sudo!" >&2
    exit 1
fi

PATH="${PATH}:$(dirname "$BASH_SOURCE")/bin"
REBOOT_REQUIRED=0

SCRIPT_DIR="$(dirname "$BASH_SOURCE")/scripts"

# Source all components
source "${SCRIPT_DIR}/01-system-packages.sh"
source "${SCRIPT_DIR}/02-raspi-config.sh"
source "${SCRIPT_DIR}/03-udev-rules.sh"
source "${SCRIPT_DIR}/04-fetch-images.sh"
source "${SCRIPT_DIR}/05-docker-services.sh"
source "${SCRIPT_DIR}/06-python-env.sh"
source "${SCRIPT_DIR}/07-power-on-test.sh"
source "${SCRIPT_DIR}/08-tailscale.sh"

# Execute functions
setup_system_packages
setup_tailscale
setup_raspi_config
setup_udev_rules
fetch_test_images
setup_docker_services
setup_python_env
setup_power_on_test

if [ "$REBOOT_REQUIRED" -eq 1 ]; then
    if [ -t 0 ]; then
        read -r -p "I2C, SPI and UART are configured. Reboot now? [y/N] " REBOOT_NOW
        if [[ "$REBOOT_NOW" =~ ^[Yy]$ ]]; then
            sudo reboot
        else
            echo "I2C, SPI and UART configuration will apply after the next reboot."
        fi
    else
        echo "I2C, SPI and UART are configured. Reboot the Raspberry Pi to apply them."
    fi
fi
