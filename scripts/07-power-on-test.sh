#!/usr/bin/env bash

setup_power_on_test() {
    local repo_dir
    local run_user
    local couchdb_service_template
    local power_on_service_template
    local render_dir
    local couchdb_service_rendered
    local power_on_service_rendered
    local escaped_repo_dir
    local escaped_run_user

    repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    run_user="$(id -un)"
    couchdb_service_template="${repo_dir}/deploy/cm5-couchdb.service.in"
    power_on_service_template="${repo_dir}/deploy/cm5-power-on-test.service.in"

    for service_file in \
        "${couchdb_service_template}" \
        "${power_on_service_template}"; do
        if [ ! -f "${service_file}" ]; then
            echo "ERROR: Service template was not found: ${service_file}" >&2
            return 1
        fi
    done

    case "${run_user}" in
        "" | *[!A-Za-z0-9_.-]*)
            echo "ERROR: Unsupported service user name: ${run_user}" >&2
            return 1
            ;;
    esac

    case "${repo_dir}" in
        *$'\n'* | *$'\r'*)
            echo "ERROR: Repository path contains a newline." >&2
            return 1
            ;;
    esac

    # Escape systemd specifier markers, then sed replacement characters.
    escaped_repo_dir="${repo_dir//%/%%}"
    escaped_repo_dir="$(
        printf '%s' "${escaped_repo_dir}" \
            | sed -e 's/\\/\\\\/g' -e 's/[&|]/\\&/g'
    )"
    escaped_run_user="$(
        printf '%s' "${run_user}" \
            | sed -e 's/\\/\\\\/g' -e 's/[&|]/\\&/g'
    )"

    render_dir="$(mktemp -d)"
    couchdb_service_rendered="${render_dir}/cm5-couchdb.service"
    power_on_service_rendered="${render_dir}/cm5-power-on-test.service"

    if ! sed \
        -e "s|@REPO_DIR@|${escaped_repo_dir}|g" \
        -e "s|@RUN_USER@|${escaped_run_user}|g" \
        "${couchdb_service_template}" > "${couchdb_service_rendered}"; then
        rm -f -- "${couchdb_service_rendered}" "${power_on_service_rendered}"
        rmdir -- "${render_dir}" 2>/dev/null || true
        return 1
    fi

    if ! sed \
        -e "s|@REPO_DIR@|${escaped_repo_dir}|g" \
        -e "s|@RUN_USER@|${escaped_run_user}|g" \
        "${power_on_service_template}" > "${power_on_service_rendered}"; then
        rm -f -- "${couchdb_service_rendered}" "${power_on_service_rendered}"
        rmdir -- "${render_dir}" 2>/dev/null || true
        return 1
    fi

    if command -v systemd-analyze >/dev/null 2>&1; then
        if ! systemd-analyze verify \
            "${couchdb_service_rendered}" \
            "${power_on_service_rendered}"; then
            echo "ERROR: Generated systemd service validation failed." >&2
            rm -f -- "${couchdb_service_rendered}" "${power_on_service_rendered}"
            rmdir -- "${render_dir}" 2>/dev/null || true
            return 1
        fi
    fi

    echo "Installing and enabling the CouchDB and power-on HardPy services..."
    sudo install -m 0644 "${couchdb_service_rendered}" \
        /etc/systemd/system/cm5-couchdb.service
    sudo install -m 0644 "${power_on_service_rendered}" \
        /etc/systemd/system/cm5-power-on-test.service

    rm -f -- "${couchdb_service_rendered}" "${power_on_service_rendered}"
    rmdir -- "${render_dir}"

    sudo systemctl daemon-reload
    sudo systemctl enable --now cm5-couchdb.service
    sudo systemctl enable cm5-power-on-test.service
}
