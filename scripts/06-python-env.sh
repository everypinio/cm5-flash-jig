#!/usr/bin/env bash

setup_python_env() {
    echo "Creating the Python virtual environment (.venv) and installing dependencies from requirements.txt..."
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi
    
    source .venv/bin/activate
    pip3 install -r requirements.txt
}
