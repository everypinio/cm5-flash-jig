#!/usr/bin/env bash

setup_udev_rules() {
    echo "Configuring udev permissions for the powerblock and DUT UART..."
    
    sudo tee /etc/udev/rules.d/99-pwrblock.rules >/dev/null <<'EOF'
SUBSYSTEM=="usb", ATTR{idVendor}=="caff", ATTR{idProduct}=="4000", MODE="0660", GROUP="plugdev"
KERNEL=="usbtmc[0-9]*", ATTRS{idVendor}=="caff", ATTRS{idProduct}=="4000", MODE="0660", GROUP="plugdev"
EOF

    sudo tee /etc/udev/rules.d/10-cm-flasher-uart.rules >/dev/null <<'EOF'
SUBSYSTEM=="tty", KERNEL=="ttyAMA[0-9]*", MODE="0660", GROUP="dialout", RUN+="/bin/sh -c 'chgrp dialout /dev/%k && chmod 0660 /dev/%k'"
EOF
    sudo rm -f /etc/udev/rules.d/99-cm-flasher-uart.rules
    
    sudo usermod -aG plugdev "$USER"
    sudo usermod -aG dialout "$USER"
    sudo modprobe usbtmc
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    sudo udevadm settle

    UART_DEVICE="$(readlink -f /dev/serial0 2>/dev/null || true)"
    if [ -c "$UART_DEVICE" ]; then
        sudo chgrp dialout "$UART_DEVICE"
        sudo chmod 0660 "$UART_DEVICE"
    fi
}
