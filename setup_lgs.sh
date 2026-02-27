#!/bin/bash
# ===========================================
# LGS-Gateway Auto Setup Script
# ===========================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_FILE="$PROJECT_DIR/systemd/lgs_gateway.service"
VENV_DIR="$PROJECT_DIR/venv"

echo "========================================="
echo " LGS-Gateway Installer"
echo "========================================="

# ตรวจสอบสิทธิ์ root
if [ "$EUID" -ne 0 ]; then
  echo "[ERROR] กรุณารันด้วย sudo: sudo ./setup_lgs.sh"
  exit 1
fi

# 1) อัปเดตระบบ
echo "[1/5] อัปเดตระบบ..."
apt-get update -y

# 2) ติดตั้ง Python3 และ pip
echo "[2/5] ติดตั้ง Python3, pip, venv..."
apt-get install -y python3 python3-pip python3-venv

# 3) สร้าง Virtual Environment และติดตั้ง Library
echo "[3/5] สร้าง Virtual Environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$PROJECT_DIR/requirements.txt"
deactivate

# 4) ติดตั้ง Systemd Service
echo "[4/5] ติดตั้ง Systemd Service..."
cp "$SERVICE_FILE" /etc/systemd/system/lgs_gateway.service
systemctl daemon-reload
systemctl enable lgs_gateway.service

# 5) เริ่มต้น Service
echo "[5/5] เริ่มต้น Service..."
systemctl start lgs_gateway.service

echo ""
echo "========================================="
echo " ติดตั้งเสร็จสมบูรณ์!"
echo "========================================="
echo " ตรวจสอบสถานะ: sudo systemctl status lgs_gateway"
echo " ดู Log:       sudo journalctl -u lgs_gateway -f"
echo "========================================="
