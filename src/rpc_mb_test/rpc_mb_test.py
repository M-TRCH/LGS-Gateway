"""
LGS Modbus RPC Test — ทดสอบทุก Function Code ผ่าน Bridge RPC
FC01: Read Coils              FC02: Read Discrete Inputs
FC03: Read Holding Registers  FC04: Read Input Registers
FC05: Write Single Coil       FC06: Write Single Register
FC15: Write Multiple Coils    FC16: Write Multiple Registers
"""
import time
from arduino.app_utils import Bridge, App

SLAVE_ID = 14   # slave ที่จะทดสอบ
TEST_ADDR = 1001

# ==================== Helper ====================
def hex_to_registers(hex_str: str) -> list[int]:
    """แปลง hex string เป็น list ของ 16-bit register values"""
    regs = []
    for i in range(0, len(hex_str), 4):
        regs.append(int(hex_str[i:i+4], 16))
    return regs

def hex_to_bits(hex_str: str, quantity: int) -> list[int]:
    """แปลง hex string เป็น list ของ bit values (0/1)"""
    bits = []
    for i in range(0, len(hex_str), 2):
        byte_val = int(hex_str[i:i+2], 16)
        for b in range(8):
            if len(bits) < quantity:
                bits.append((byte_val >> b) & 1)
    return bits

# ==================== Test Functions ====================
def test_fc05_write_single_coil():
    """FC05: Write Single Coil — เปิด/ปิดตู้ยา"""
    print("\n" + "="*50)
    print("📝 FC05: Write Single Coil")
    print("="*50)
    for val in [1, 0]:
        label = "ON" if val else "OFF"
        print(f"  สั่ง ID:{SLAVE_ID} Addr:{TEST_ADDR} → {label} ...", end=" ", flush=True)
        try:
            result = Bridge.call("write_coil", SLAVE_ID, TEST_ADDR, val)
            print("✅ สำเร็จ" if result == 1 else "❌ ล้มเหลว")
        except Exception as e:
            print(f"⚠️ {e}")
        time.sleep(0.5)

def test_fc06_write_single_register():
    """FC06: Write Single Register — เขียนค่า register"""
    print("\n" + "="*50)
    print("📝 FC06: Write Single Register")
    print("="*50)
    fc06_addr = 110
    for val in range(0, 101, 25):   # 0, 25, 50, 75, 100
        print(f"  เขียน ID:{SLAVE_ID} Addr:{fc06_addr} = {val} ...", end=" ", flush=True)
        try:
            result = Bridge.call("write_register", SLAVE_ID, fc06_addr, val)
            print("✅ สำเร็จ" if result == 1 else "❌ ล้มเหลว")
        except Exception as e:
            print(f"⚠️ {e}")
        time.sleep(0.5)

def test_fc01_read_coils():
    """FC01: Read Coils — อ่านสถานะ coils"""
    print("\n" + "="*50)
    print("📖 FC01: Read Coils")
    print("="*50)
    quantity = 8
    print(f"  อ่าน ID:{SLAVE_ID} Addr:{TEST_ADDR} Qty:{quantity} ...", end=" ", flush=True)
    try:
        hex_data = Bridge.call("read_coils", SLAVE_ID, TEST_ADDR, quantity)
        if hex_data:
            bits = hex_to_bits(hex_data, quantity)
            print(f"✅ Hex={hex_data} Bits={bits}")
        else:
            print("❌ ไม่มี response")
    except Exception as e:
        print(f"⚠️ {e}")

def test_fc02_read_discrete_inputs():
    """FC02: Read Discrete Inputs"""
    print("\n" + "="*50)
    print("📖 FC02: Read Discrete Inputs")
    print("="*50)
    fc02_addr = 0
    quantity = 1
    print(f"  อ่าน ID:{SLAVE_ID} Addr:{fc02_addr} Qty:{quantity} ...", end=" ", flush=True)
    try:
        hex_data = Bridge.call("read_discrete_inputs", SLAVE_ID, fc02_addr, quantity)
        if hex_data:
            bits = hex_to_bits(hex_data, quantity)
            print(f"✅ Hex={hex_data} Bits={bits}")
        else:
            print("❌ ไม่มี response")
    except Exception as e:
        print(f"⚠️ {e}")

def test_fc03_read_holding_registers():
    """FC03: Read Holding Registers"""
    print("\n" + "="*50)
    print("📖 FC03: Read Holding Registers")
    print("="*50)
    fc03_addr = 0
    quantity = 5
    print(f"  อ่าน ID:{SLAVE_ID} Addr:{fc03_addr} Qty:{quantity} ...", end=" ", flush=True)
    try:
        hex_data = Bridge.call("read_holding_registers", SLAVE_ID, fc03_addr, quantity)
        if hex_data:
            regs = hex_to_registers(hex_data)
            print(f"✅ Hex={hex_data} Values={regs}")
        else:
            print("❌ ไม่มี response")
    except Exception as e:
        print(f"⚠️ {e}")

def test_fc04_read_input_registers():
    """FC04: Read Input Registers"""
    print("\n" + "="*50)
    print("📖 FC04: Read Input Registers")
    print("="*50)
    fc04_addr = 0
    quantity = 1
    print(f"  อ่าน ID:{SLAVE_ID} Addr:{fc04_addr} Qty:{quantity} ...", end=" ", flush=True)
    try:
        hex_data = Bridge.call("read_input_registers", SLAVE_ID, fc04_addr, quantity)
        if hex_data:
            regs = hex_to_registers(hex_data)
            print(f"✅ Hex={hex_data} Values={regs}")
        else:
            print("❌ ไม่มี response")
    except Exception as e:
        print(f"⚠️ {e}")

def test_fc15_write_multiple_coils():
    """FC15: Write Multiple Coils — เขียนหลาย coils พร้อมกัน (Qty ≤ 8)"""
    print("\n" + "="*50)
    print("📝 FC15: Write Multiple Coils")
    print("="*50)
    quantity = 8     # ≤ 8 coils → 1 data byte
    hex_data = "CD"  # bits: 1,0,1,1,0,0,1,1 = 0xCD
    print(f"  เขียน ID:{SLAVE_ID} Addr:{TEST_ADDR} Qty:{quantity} Data={hex_data} ...", end=" ", flush=True)
    try:
        result = Bridge.call("write_coils", SLAVE_ID, TEST_ADDR, quantity, hex_data)
        print("✅ สำเร็จ" if result == 1 else "❌ ล้มเหลว")
    except Exception as e:
        print(f"⚠️ {e}")

def test_fc16_write_multiple_registers():
    """FC16: Write Multiple Registers — เขียนหลาย registers พร้อมกัน (Qty ≤ 5)"""
    print("\n" + "="*50)
    print("📝 FC16: Write Multiple Registers")
    print("="*50)
    fc16_addr = 110
    quantity = 5   # ≤ 5 registers
    hex_data = "000A0064001400280032"  # reg: 10, 100, 20, 40, 50
    print(f"  เขียน ID:{SLAVE_ID} Addr:{fc16_addr} Qty:{quantity} Data={hex_data} ...", end=" ", flush=True)
    try:
        result = Bridge.call("write_registers", SLAVE_ID, fc16_addr, quantity, hex_data)
        print("✅ สำเร็จ" if result == 1 else "❌ ล้มเหลว")
    except Exception as e:
        print(f"⚠️ {e}")

# ==================== Main Loop ====================
def loop():
    print("\n" + "#"*50)
    print("# Modbus Full Function Code Test Suite")
    print("#"*50)

    # Write tests
    test_fc05_write_single_coil()
    test_fc06_write_single_register()
    test_fc15_write_multiple_coils()
    test_fc16_write_multiple_registers()

    # Read tests
    test_fc01_read_coils()
    test_fc02_read_discrete_inputs()
    test_fc03_read_holding_registers()
    test_fc04_read_input_registers()

    print("\n" + "="*50)
    print("🏁 ทดสอบครบทุก FC แล้ว — รอ 10 วินาทีก่อนรอบถัดไป")
    print("="*50)
    time.sleep(10)

if __name__ == "__main__":
    print("🚀 Starting Full Modbus Test Suite...")
    App.run(user_loop=loop)