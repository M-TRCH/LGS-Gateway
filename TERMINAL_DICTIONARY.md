# Arduino Uno Q Terminal Dictionary
**พจนานุกรมคำสั่ง Terminal สำหรับการพัฒนาระบบ Modbus Gateway บนบอร์ด Arduino Uno Q (Debian Linux)**
*อัปเดตล่าสุด: เฟสการติดตั้งและทดสอบระบบ LGS*

---

## 1. System & Package Management (การจัดการระบบและแพ็กเกจ)

| คำสั่ง (Command) | คำอธิบาย (Description) |
| :--- | :--- |
| `sudo apt update` | อัปเดตรายการแพ็กเกจ (package index) ของระบบปฏิบัติการให้ตรงกับ Repository ล่าสุด |
| `sudo apt install python3 python3-pip python3-venv -y` | ติดตั้ง Python 3, ตัวจัดการแพ็กเกจ pip และเครื่องมือสร้าง Virtual Environment โดยข้ามการยืนยัน (`-y`) |
| `pwd` | แสดง Working Directory ปัจจุบัน (Print Working Directory) เช่น `/home/arduino/lgs_gateway` |

---

## 2. Python & Virtual Environment (การจัดการสภาพแวดล้อม Python)

| คำสั่ง (Command) | คำอธิบาย (Description) |
| :--- | :--- |
| `mkdir ~/lgs_gateway` | สร้างไดเรกทอรี `lgs_gateway` ภายใต้ Home directory (`~`) |
| `cd ~/lgs_gateway` | เปลี่ยน Working Directory ไปยังไดเรกทอรี `lgs_gateway` |
| `python3 -m venv venv` | สร้าง Virtual Environment ชื่อ `venv` เพื่อแยกการจัดการไลบรารีของโปรเจกต์ออกจากระบบหลัก |
| `source venv/bin/activate` | **[จำเป็น]** เปิดใช้งาน Virtual Environment — ต้องดำเนินการทุกครั้งก่อนรันสคริปต์หรือติดตั้งไลบรารีเพิ่มเติม |
| `pip install pymodbus pyserial` | ติดตั้งไลบรารี pymodbus (Modbus TCP/RTU) และ pyserial (Serial Communication) |
| `python3 modbus_gateway.py` | รันสคริปต์ Gateway โดยตรง (สำหรับการทดสอบด้วยตนเอง) |

---

## 3. RS485 & Serial Port Management (การจัดการพอร์ตสื่อสาร)

| คำสั่ง (Command) | คำอธิบาย (Description) |
| :--- | :--- |
| `ls /dev/ttyUSB* /dev/ttyACM*` | แสดงรายชื่อพอร์ต USB-to-Serial ที่ระบบตรวจพบ (เช่น `/dev/ttyUSB0`) |
| `sudo dmesg \| grep tty` | ตรวจสอบ Kernel Log เพื่อระบุอุปกรณ์ Serial ที่เชื่อมต่อล่าสุด |
| `python3 -m serial.tools.list_ports` | สแกนและแสดงรายชื่อพอร์ต Serial ทั้งหมดที่ระบบรู้จัก พร้อมรายละเอียดอุปกรณ์ |
| `sudo usermod -a -G dialout $USER` | **[แก้ไข Permission]** เพิ่มผู้ใช้ปัจจุบันเข้ากลุ่ม `dialout` เพื่อให้สามารถอ่าน/เขียนพอร์ต Serial ได้ — ต้อง Logout แล้ว Login ใหม่จึงจะมีผล |

---

## 4. Git & Version Control (การจัดการเวอร์ชันซอร์สโค้ด)

| คำสั่ง (Command) | คำอธิบาย (Description) |
| :--- | :--- |
| `git --version` | ตรวจสอบเวอร์ชัน Git ที่ติดตั้งอยู่ในระบบ |
| `sudo apt install git -y` | ติดตั้ง Git บนบอร์ด |
| `git config --global user.name "..."` | กำหนดชื่อผู้ใช้ Git ระดับ Global สำหรับบันทึก Commit |
| `git config --global user.email "..."` | กำหนดอีเมลผู้ใช้ Git ระดับ Global สำหรับบันทึก Commit |
| `git clone <URL>` | โคลน Repository จาก Remote มายังบอร์ด (เช่น `git clone https://github.com/...`) |

---

## 5. Systemd Service (การกำหนดค่า Background Service)

| คำสั่ง (Command) | คำอธิบาย (Description) |
| :--- | :--- |
| `sudo nano /etc/systemd/system/lgs_gateway.service` | สร้างหรือแก้ไขไฟล์ Unit Configuration ของ Gateway Service |
| `sudo systemctl daemon-reload` | โหลดไฟล์ Unit Configuration ใหม่ — จำเป็นต้องดำเนินการทุกครั้งหลังแก้ไขไฟล์ `.service` |
| `sudo systemctl enable lgs_gateway.service` | กำหนดให้ Service เริ่มทำงานอัตโนมัติเมื่อบอร์ดบูต (Auto-start on boot) |
| `sudo systemctl start lgs_gateway.service` | เริ่มการทำงานของ Service ทันที |
| `sudo systemctl stop lgs_gateway.service` | หยุดการทำงานของ Service |
| `sudo systemctl restart lgs_gateway.service` | รีสตาร์ต Service — ใช้หลังจากแก้ไขไฟล์ `.py` เพื่อให้โค้ดที่อัปเดตมีผล |
| `sudo systemctl status lgs_gateway.service` | ตรวจสอบสถานะของ Service (Active / Inactive / Failed) |

---

## 6. Log Monitoring (การตรวจสอบ Log และวิเคราะห์ข้อผิดพลาด)

| คำสั่ง (Command) | คำอธิบาย (Description) |
| :--- | :--- |
| `sudo journalctl -u lgs_gateway.service -f` | แสดง Log ของ Gateway แบบ Real-time (กด `Ctrl + C` เพื่อหยุด) |
| `sudo journalctl -u lgs_gateway.service -n 50` | แสดง Log ย้อนหลัง 50 บรรทัดล่าสุด |
| `sudo journalctl -u lgs_gateway.service --since "1 hour ago"` | แสดง Log ของ Service ย้อนหลัง 1 ชั่วโมง |
| `sudo journalctl -u lgs_gateway.service --no-pager` | แสดง Log ทั้งหมดโดยไม่ใช้ Pager (แสดงผลต่อเนื่องไม่ต้องกด Space) |

---

## 7. Deployment & Setup Script (การ Deploy และติดตั้งระบบ)

| คำสั่ง (Command) | คำอธิบาย (Description) |
| :--- | :--- |
| `chmod +x setup_lgs.sh` | กำหนดสิทธิ์ Execute ให้กับสคริปต์ติดตั้งอัตโนมัติ |
| `./setup_lgs.sh` | รันสคริปต์ Deploy อัตโนมัติ — ติดตั้ง Dependencies, สร้าง venv, ติดตั้ง Service ในคำสั่งเดียว |
| `pip install -r requirements.txt` | ติดตั้งไลบรารีทั้งหมดตาม `requirements.txt` (pymodbus, pyserial) |
| `pip install --upgrade -r requirements.txt` | อัปเกรดไลบรารีทั้งหมดให้ตรงกับเวอร์ชันที่ระบุใน `requirements.txt` |
| `pip freeze` | แสดงรายการไลบรารีและเวอร์ชันที่ติดตั้งอยู่ใน Virtual Environment ปัจจุบัน |
| `pip show pymodbus` | แสดงรายละเอียดของไลบรารี pymodbus (เวอร์ชัน, ที่ตั้งไฟล์, Dependencies) |
| `sudo cp systemd/lgs_gateway.service /etc/systemd/system/` | คัดลอกไฟล์ Service Configuration ไปยัง Systemd directory ของระบบ |

---

## 8. Network & Modbus TCP Testing (การทดสอบเครือข่ายและ Modbus TCP)

| คำสั่ง (Command) | คำอธิบาย (Description) |
| :--- | :--- |
| `hostname -I` | แสดง IP Address ของบอร์ดทั้งหมด — ใช้สำหรับตั้งค่า Modbus TCP Client เชื่อมต่อเข้ามา |
| `ip addr show` | แสดงรายละเอียด Network Interface ทั้งหมด (IP, MAC, สถานะ) |
| `ss -tlnp \| grep 502` | ตรวจสอบว่ามี Process ใด Listening บนพอร์ต 502 (Modbus TCP) หรือ 1502 |
| `ss -tlnp \| grep 1502` | ตรวจสอบว่า Gateway กำลัง Listening บนพอร์ต 1502 (Fallback port เมื่อไม่ได้รันเป็น root) |
| `sudo lsof -i :502` | แสดง Process ที่ใช้งานพอร์ต 502 พร้อม PID — ใช้ตรวจสอบ Port conflict |
| `ping <IP_ADDRESS>` | ทดสอบการเชื่อมต่อเครือข่ายไปยังอุปกรณ์ปลายทาง |
| `curl -v telnet://<IP>:502` | ทดสอบว่าสามารถเชื่อมต่อ TCP ไปยัง Modbus server ได้หรือไม่ |

---

## 9. Process & Resource Monitoring (การตรวจสอบ Process และทรัพยากร)

| คำสั่ง (Command) | คำอธิบาย (Description) |
| :--- | :--- |
| `ps aux \| grep modbus_gateway` | ค้นหา Process ของ Gateway ที่กำลังทำงาน — แสดง PID, CPU%, MEM% |
| `top -bn1 \| head -20` | แสดงภาพรวมการใช้ทรัพยากร (CPU, RAM) ของระบบแบบ Snapshot |
| `free -h` | แสดงการใช้งาน RAM ของระบบในรูปแบบอ่านง่าย (Human-readable) |
| `df -h` | แสดงพื้นที่ดิสก์ที่ใช้งานและเหลืออยู่ |
| `uptime` | แสดงระยะเวลาที่ระบบทำงานต่อเนื่อง (Uptime) และค่า Load Average |
| `kill <PID>` | หยุด Process ด้วย PID ที่ระบุ — ใช้เมื่อต้องการ Kill กระบวนการค้าง |
| `sudo kill -9 <PID>` | บังคับหยุด Process ทันที (Force Kill) — ใช้เมื่อ `kill` ปกติไม่ได้ผล |

---

## 10. File & Project Management (การจัดการไฟล์โปรเจกต์)

| คำสั่ง (Command) | คำอธิบาย (Description) |
| :--- | :--- |
| `ls -la` | แสดงรายชื่อไฟล์ทั้งหมดรวมไฟล์ซ่อน พร้อม Permission, ขนาด และวันที่แก้ไข |
| `cat src/modbus_gateway.py` | แสดงเนื้อหาไฟล์ Gateway ทั้งหมดบน Terminal |
| `nano src/modbus_gateway.py` | แก้ไขไฟล์ Gateway ด้วย Text Editor (nano) |
| `cat requirements.txt` | ดูรายการ Dependencies และเวอร์ชันที่โปรเจกต์ต้องการ |
| `cat systemd/lgs_gateway.service` | ดูการตั้งค่า Systemd Service ของ Gateway |
| `tail -f /var/log/syslog` | ดู System Log แบบ Real-time — ช่วยวิเคราะห์ปัญหาระดับ OS |
| `chmod +x <file>` | กำหนดสิทธิ์ Execute ให้กับไฟล์สคริปต์ |

---

## 11. Troubleshooting (การแก้ไขปัญหาที่พบบ่อย)

| ปัญหา (Problem) | คำสั่งแก้ไข (Solution Command) | คำอธิบาย |
| :--- | :--- | :--- |
| Port 502 ต้องการสิทธิ์ root | `sudo python3 src/modbus_gateway.py` | รันด้วยสิทธิ์ root เพื่อ Bind พอร์ต < 1024 (หรือใช้พอร์ต 1502 แทน) |
| Permission denied บนพอร์ต Serial | `sudo usermod -a -G dialout $USER && logout` | เพิ่มสิทธิ์เข้ากลุ่ม dialout แล้ว Logout/Login ใหม่ |
| ไลบรารี import ไม่ได้ (ImportError) | `source venv/bin/activate && pip install -r requirements.txt` | ตรวจสอบว่าเปิดใช้ venv แล้วติดตั้ง Dependencies ใหม่ |
| Service ไม่เริ่มทำงาน | `sudo systemctl status lgs_gateway.service` | ตรวจสอบ Error message จาก Systemd |
| พอร์ต Serial หาไม่เจอ | `ls /dev/ttyUSB* && sudo dmesg \| tail -20` | ตรวจสอบว่าอุปกรณ์ USB-to-Serial เชื่อมต่ออยู่ |
| เวอร์ชัน pymodbus ไม่ตรง | `pip show pymodbus && pip install pymodbus==3.12.1` | ตรวจสอบและติดตั้งเวอร์ชันที่ถูกต้อง |
| Gateway ค้างไม่ตอบสนอง | `sudo systemctl restart lgs_gateway.service` | รีสตาร์ต Service เพื่อ Reset สถานะ |
