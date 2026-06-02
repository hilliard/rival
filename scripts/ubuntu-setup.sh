#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/opt/rival}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "[rival] Installing system packages..."
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip postgresql postgresql-contrib

echo "[rival] Preparing app directory: ${APP_DIR}"
sudo mkdir -p "${APP_DIR}"
sudo chown -R "$USER:$USER" "${APP_DIR}"

echo "[rival] Creating venv and installing app..."
cd "${APP_DIR}"
${PYTHON_BIN} -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

echo "[rival] Setup complete."
echo "Next steps:"
echo "1) Create ${APP_DIR}/.env.production with real values"
echo "2) Run: source ${APP_DIR}/.venv/bin/activate && haynesworld-rival init-db"
echo "3) Install systemd units from deploy/systemd"
