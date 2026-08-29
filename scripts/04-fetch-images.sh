#!/usr/bin/env bash

fetch_test_images() {
    echo "Fetching test images: Raspberry Pi OS Lite (raspios) - Release 2026-04-21..."
    
    IMAGE_DIR="${HOME}/images"
    IMAGE_PATH="${IMAGE_DIR}/cm5-test.img.xz"
    IMAGE_URL="https://downloads.raspberrypi.com/raspios_lite_arm64/images/raspios_lite_arm64-2026-04-21/2026-04-21-raspios-trixie-arm64-lite.img.xz"
    IMAGE_SHA256="4cd31df026fd82243805a326dc0cafd7383f7e3d30c9413e7044d507aae281e2"

    mkdir -p "$IMAGE_DIR"
    if [ ! -f "$IMAGE_PATH" ]; then
        echo "Downloading $IMAGE_URL ..."
        curl --fail --location --output "${IMAGE_PATH}.tmp" "$IMAGE_URL"
        printf '%s  %s\n' "$IMAGE_SHA256" "${IMAGE_PATH}.tmp" | sha256sum --check
        mv "${IMAGE_PATH}.tmp" "$IMAGE_PATH"
        echo "Download complete."
    else
        echo "Image already exists at $IMAGE_PATH"
    fi
}
