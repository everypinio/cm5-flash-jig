#!/usr/bin/env bash

setup_docker_services() {
    echo "Enabling the Docker systemd service at startup and starting the Docker Compose services..."
    sudo systemctl enable --now docker
    sudo docker-compose up -d
}
