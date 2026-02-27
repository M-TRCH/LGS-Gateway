# LGS-Gateway

Modbus RTU to TCP Gateway สำหรับอ่านข้อมูลจากอุปกรณ์ผ่าน Serial Port และให้บริการผ่าน Modbus TCP

## โครงสร้างโปรเจค

```
LGS-Gateway/
├── .gitignore
├── README.md
├── requirements.txt
├── setup_lgs.sh
├── systemd/
│   └── lgs_gateway.service
└── src/
    └── modbus_gateway.py
```

## ความต้องการของระบบ

- Python 3.7+
- Raspberry Pi (หรือ Linux ที่มี Serial Port)

## การติดตั้ง

### วิธีที่ 1: ติดตั้งอัตโนมัติด้วยสคริปต์

```bash
chmod +x setup_lgs.sh
sudo ./setup_lgs.sh
```

### วิธีที่ 2: ติดตั้งด้วยตนเอง

1. สร้าง Virtual Environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

2. ติดตั้ง Library:
```bash
pip install -r requirements.txt
```

3. รันโปรแกรม:
```bash
python src/modbus_gateway.py
```

## การตั้งค่า Systemd Service

คัดลอกไฟล์ Service ไปยัง systemd:
```bash
sudo cp systemd/lgs_gateway.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable lgs_gateway.service
sudo systemctl start lgs_gateway.service
```

ตรวจสอบสถานะ:
```bash
sudo systemctl status lgs_gateway.service
```

ดู Log:
```bash
sudo journalctl -u lgs_gateway.service -f
```

## คำสั่ง Terminal ที่ใช้บ่อย

| คำสั่ง | คำอธิบาย |
|--------|----------|
| `sudo systemctl start lgs_gateway` | เริ่มต้น Service |
| `sudo systemctl stop lgs_gateway` | หยุด Service |
| `sudo systemctl restart lgs_gateway` | รีสตาร์ท Service |
| `sudo systemctl status lgs_gateway` | ตรวจสอบสถานะ |
| `sudo journalctl -u lgs_gateway -f` | ดู Log แบบ Real-time |
