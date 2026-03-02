#!/bin/bash
set -euo pipefail
# =============================================================
# LGS Gateway v2.0 - Automated Deployment Script
# =============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="lgs_gateway"
SERVICE_USER="lgs-gateway"
INSTALL_DIR="$SCRIPT_DIR"
VENV_DIR="$INSTALL_DIR/venv"
SERIAL_PORT="${LGS_SERIAL_PORT:-/dev/ttyUSB0}"

echo "========================================"
echo "  LGS Gateway v2.0 Setup"
echo "========================================"

# ------ 1. OS packages ------
echo "[1/6] Installing OS packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv

# ------ 2. Dedicated service user ------
echo "[2/6] Creating service user ($SERVICE_USER)..."
if ! id "$SERVICE_USER" &>/dev/null; then
    sudo useradd -r -s /usr/sbin/nologin -d "$INSTALL_DIR" "$SERVICE_USER"
    echo "  Created user: $SERVICE_USER"
else
    echo "  User $SERVICE_USER already exists"
fi

# Grant serial port access (dialout group)
sudo usermod -aG dialout "$SERVICE_USER" 2>/dev/null || true

# ------ 3. Python virtual environment ------
echo "[3/6] Setting up Python virtual environment..."
python3 -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -r "$INSTALL_DIR/requirements.txt"
deactivate

# ------ 4. Config directory ------
echo "[4/6] Setting up configuration..."
sudo mkdir -p /etc/lgs_gateway
if [ ! -f /etc/lgs_gateway/config.yaml ]; then
    sudo cp "$INSTALL_DIR/config.yaml" /etc/lgs_gateway/config.yaml
    echo "  Installed config to /etc/lgs_gateway/config.yaml"
else
    echo "  Config already exists -- skipping (merge manually if needed)"
fi

# Ensure the config file is owned by the service user
sudo chown "$SERVICE_USER":"$SERVICE_USER" /etc/lgs_gateway/config.yaml
sudo chmod 640 /etc/lgs_gateway/config.yaml

# ------ 5. Verify serial port ------
echo "[5/6] Checking serial port..."
if [ -e "$SERIAL_PORT" ]; then
    echo "  $SERIAL_PORT found"
else
    echo "  WARNING: $SERIAL_PORT not found -- gateway will retry at runtime"
fi

# ------ 6. Systemd service ------
echo "[6/6] Installing systemd service..."
sudo cp "$INSTALL_DIR/systemd/lgs_gateway.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME.service"
sudo systemctl restart "$SERVICE_NAME.service"

echo ""
echo "========================================"
echo "  Deployment Complete!"
echo "========================================"
echo ""
echo "  Status : sudo systemctl status $SERVICE_NAME"
echo "  Logs   : sudo journalctl -u $SERVICE_NAME -f"
echo "  Config : /etc/lgs_gateway/config.yaml"
echo "  Health : curl http://localhost:8080/"
echo ""