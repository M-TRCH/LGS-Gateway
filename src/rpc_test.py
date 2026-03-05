import time
import random
from arduino.app_utils import App, Bridge

# ฟังก์ชันนี้รอให้ฝั่ง C++ (MCU) โยนข้อความกลับมาโชว์
def print_log(msg: str):
    print(f"👉 [MCU Log]: {msg}")

# ลูปหลักของ Python
def loop():
    print("\n--- Sending Random Request to MCU ---")

    try:
        # สุ่มตัวเลขสองตัวแล้วส่งไปให้ MCU คำนวณ
        a = random.randint(0, 100)
        b = random.randint(0, 100)
        print(f"🔢 [Python] Sending: {a}, {b}")
        result = Bridge.call("add_numbers", a, b)
        print(f"✅ [Python] MCU returned result: {a} + {b} = {result}")

    except Exception as e:
        print(f"❌ [Python] RPC Error: {e}")

    time.sleep(2)  # หน่วงเวลา 2 วินาทีก่อนเรียกซ้ำ

# ลงทะเบียนฟังก์ชัน 'print_log' ให้ C++ มองเห็น
Bridge.provide("print_log", print_log)

if __name__ == "__main__":
    print("Starting RPC Test App...")
    # เริ่มรันแอปพลิเคชัน
    App.run(user_loop=loop)