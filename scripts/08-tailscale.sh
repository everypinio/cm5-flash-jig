#!/usr/bin/env bash

setup_tailscale() {
    local distro_id
    local distro_like
    local keyring_tmp
    local repo_base_url
    local repo_list_tmp
    local version_codename

    if [ ! -r /etc/os-release ]; then
        echo "ERROR: Cannot detect the operating system for Tailscale setup." >&2
        return 1
    fi

    # shellcheck disable=SC1091
    source /etc/os-release
    distro_id="${ID:-}"
    distro_like="${ID_LIKE:-}"
    version_codename="${VERSION_CODENAME:-}"

    if [[ "${distro_id}" != "debian" && "${distro_id}" != "raspbian" \
        && " ${distro_like} " != *" debian "* ]]; then
        echo "ERROR: Tailscale bootstrap currently supports Debian-based systems only." >&2
        return 1
    fi
    if [ -z "${version_codename}" ]; then
        echo "ERROR: VERSION_CODENAME is missing from /etc/os-release." >&2
        return 1
    fi

    echo "Installing Tailscale for Debian ${version_codename}..."
    repo_base_url="https://pkgs.tailscale.com/stable/debian"
    keyring_tmp="$(mktemp)"
    repo_list_tmp="$(mktemp)"

    if ! curl -fsSL \
        "${repo_base_url}/${version_codename}.noarmor.gpg" \
        -o "${keyring_tmp}"; then
        rm -f -- "${keyring_tmp}" "${repo_list_tmp}"
        return 1
    fi
    if ! curl -fsSL \
        "${repo_base_url}/${version_codename}.tailscale-keyring.list" \
        -o "${repo_list_tmp}"; then
        rm -f -- "${keyring_tmp}" "${repo_list_tmp}"
        return 1
    fi

    sudo install -d -m 0755 /usr/share/keyrings /etc/apt/sources.list.d
    sudo install -m 0644 "${keyring_tmp}" \
        /usr/share/keyrings/tailscale-archive-keyring.gpg
    sudo install -m 0644 "${repo_list_tmp}" \
        /etc/apt/sources.list.d/tailscale.list
    rm -f -- "${keyring_tmp}" "${repo_list_tmp}"

    sudo apt-get update
    sudo apt-get install -y tailscale tailscale-archive-keyring
    sudo systemctl enable --now tailscaled.service

    if sudo tailscale status --json 2>/dev/null \
        | grep -q '"BackendState"[[:space:]]*:[[:space:]]*"Running"'; then
        echo "Tailscale is already authenticated."
    elif [ -t 0 ]; then
        echo "Authenticate this Raspberry Pi in Tailscale..."
        sudo tailscale up
    else
        echo "Tailscale is installed but not authenticated."
        echo "Run 'sudo tailscale up' interactively to authenticate this Raspberry Pi."
    fi
}
