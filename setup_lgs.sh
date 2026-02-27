#!/bin/bash
# LGS Gateway - Automated Deployment Script

echo "========================================"
echo "  Starting LGS Gateway Setup...  "
echo "========================================"

# 1. Update OS & Install Dependencies
echo "[1/4] Updating OS and installing required packages..."
sudo apt update
sudo apt install python3 python3-pip python3-venv -y

# 2. Setup Python Virtual Environment
echo "[2/4] Setting up Python Virtual Environment..."
python3 -m venv venv
source venv/bin/activate
echo "Installing Python libraries..."
pip install -r requirements.txt

# 3. Setup Systemd Service
echo "[3/4] Installing Systemd Service..."
sudo cp systemd/lgs_gateway.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lgs_gateway.service
sudo systemctl restart lgs_gateway.service

echo "[4/4] Deployment Complete! ✅"
echo "========================================"
echo "  Check status: sudo systemctl status lgs_gateway.service"
echo "  View logs:    sudo journalctl -u lgs_gateway.service -f"
echo "========================================"