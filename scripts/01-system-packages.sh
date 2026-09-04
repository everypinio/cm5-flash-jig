#!/usr/bin/env bash

setup_system_packages() {
    echo "Installing system packages..."
    sudo --preserve-env=PATH ./aptfile
}
