import time
from arduino.app_utils import Bridge, App

# ตัวแปรสำหรับสลับสถานะเปิด/ปิด
value_tog = True

def loop():
    global value_tog
    status_str = "ON (1)" if value_tog else "OFF (0)"
    print(f"\n--- เริ่มรอบการส่งคำสั่ง (เป้าหมาย: {status_str}) ---")
    
    # วนลูป Row (10, 20, 30) และ Col (1-8)
    for row in range(10, 40, 10):
        for col in range(1, 9):
            slave_id = row + col
            value_int = 1 if value_tog else 0
            
            print(f"📦 สั่งงานตู้ยา ID: {slave_id} ...", end=" ", flush=True)
            
            try:
                # โยน Parameter 3 ตัวข้ามไปให้ MCU (ID, Address, Value)
                result = Bridge.call("write_coil", slave_id, 1001, value_int)
                
                # ประมวลผลลัพธ์ที่ตอบกลับมาจาก C++ (1 = สำเร็จ, 0 = ล้มเหลว)
                if result == 1:
                    print("✅ สำเร็จ")
                else:
                    print("❌ ล้มเหลว (Timeout หรือไม่มีสัญญาณตอบกลับ)")
                    
            except Exception as e:
                print(f"⚠️ RPC Error: {e}")
                
            time.sleep(0.5) # หน่วงเวลาระหว่างตู้ 500ms ตามโค้ดเดิม

        time.sleep(1.5) # หน่วงเวลาหลังจบแถว 1.5 วินาที

    # สลับสถานะสำหรับลูปถัดไป
    value_tog = not value_tog
    time.sleep(2)

if __name__ == "__main__":
    print("🚀 Starting LGS-Gateway Python Manager...")
    # ให้ App.run ช่วยรันฟังก์ชัน loop() วนไปเรื่อยๆ อย่างเสถียร
    App.run(user_loop=loop)