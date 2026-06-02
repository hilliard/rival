#!/usr/bin/env bash
set -euo pipefail

APP_USER="${1:-www-data}"
APP_DIR="${2:-/opt/rival}"

echo "[rival] Installing systemd units..."
sudo cp deploy/systemd/rival-api.service /etc/systemd/system/rival-api.service
sudo cp deploy/systemd/rival-worker.service /etc/systemd/system/rival-worker.service

sudo sed -i "s|^User=.*$|User=${APP_USER}|" /etc/systemd/system/rival-api.service
sudo sed -i "s|^User=.*$|User=${APP_USER}|" /etc/systemd/system/rival-worker.service

sudo sed -i "s|^WorkingDirectory=.*$|WorkingDirectory=${APP_DIR}|" /etc/systemd/system/rival-api.service
sudo sed -i "s|^WorkingDirectory=.*$|WorkingDirectory=${APP_DIR}|" /etc/systemd/system/rival-worker.service

sudo sed -i "s|^EnvironmentFile=.*$|EnvironmentFile=${APP_DIR}/.env.production|" /etc/systemd/system/rival-api.service
sudo sed -i "s|^EnvironmentFile=.*$|EnvironmentFile=${APP_DIR}/.env.production|" /etc/systemd/system/rival-worker.service

sudo sed -i "s|^ExecStart=.*$|ExecStart=${APP_DIR}/.venv/bin/haynesworld-rival run-api|" /etc/systemd/system/rival-api.service
sudo sed -i "s|^ExecStart=.*$|ExecStart=${APP_DIR}/.venv/bin/haynesworld-rival poll-loop|" /etc/systemd/system/rival-worker.service

sudo systemctl daemon-reload
sudo systemctl enable rival-api rival-worker

echo "[rival] systemd units installed. Start with:"
echo "  sudo systemctl start rival-api rival-worker"
