#!/usr/bin/env bash

setup_power_on_test() {
    local repo_dir
    local couchdb_service_source
    local service_source

    repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    couchdb_service_source="${repo_dir}/deploy/cm5-couchdb.service"
    service_source="${repo_dir}/deploy/cm5-power-on-test.service"

    for service_file in "${couchdb_service_source}" "${service_source}"; do
        if [ ! -f "${service_file}" ]; then
            echo "ERROR: Service file was not found: ${service_file}" >&2
            return 1
        fi
    done

    echo "Installing and enabling the CouchDB and power-on HardPy services..."
    sudo install -m 0644 "${couchdb_service_source}" \
        /etc/systemd/system/cm5-couchdb.service
    sudo install -m 0644 "${service_source}" \
        /etc/systemd/system/cm5-power-on-test.service
    sudo systemctl daemon-reload
    sudo systemctl enable --now cm5-couchdb.service
    sudo systemctl enable cm5-power-on-test.service
}
