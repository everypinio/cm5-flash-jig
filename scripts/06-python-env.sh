#!/usr/bin/env bash

setup_python_env() {
    echo "Creating the Python virtual environment (.venv) and installing dependencies from requirements.txt..."
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi
    
    source .venv/bin/activate
    python -m pip install -r requirements.txt

    echo "Checking Python access to the onboard SPI current monitor..."
    python -c "import spidev; print('spidev import OK')"
}
