
// =============================================================
// LGS Modbus RTU Bridge — Full Function Code Support
// =============================================================
// FC01: Read Coils            FC02: Read Discrete Inputs
// FC03: Read Holding Regs     FC04: Read Input Registers
// FC05: Write Single Coil     FC06: Write Single Register
// FC15: Write Multiple Coils  FC16: Write Multiple Registers
// =============================================================
#include <Arduino.h>
#include <Arduino_RouterBridge.h>

#define RS485_SERIAL      Serial
#define RS485_BAUD        9600
#define MODBUS_TIMEOUT_MS 200
#define TX_BUF_SIZE       128
#define RX_BUF_SIZE       128

// ======================== CRC16 ========================
uint16_t calculateCRC(uint8_t *buf, int len)
{
  uint16_t crc = 0xFFFF;
  for (int i = 0; i < len; i++) {
    crc ^= (uint16_t)buf[i];
    for (int j = 0; j < 8; j++) {
      if (crc & 0x0001) { crc >>= 1; crc ^= 0xA001; }
      else               { crc >>= 1; }
    }
  }
  return crc;
}

// ========== ส่ง frame และรับ response กลับมา ==========
// คืนจำนวน byte ที่รับได้ (0 = timeout)
int sendAndReceive(uint8_t *tx, int txLen, uint8_t *rx, int rxMax)
{
  // ล้าง RX buffer เก่า
  while (RS485_SERIAL.available()) RS485_SERIAL.read();

  // ส่งข้อมูล
  RS485_SERIAL.write(tx, txLen);
  RS485_SERIAL.flush();

  // รอรับ response
  unsigned long lastByte = millis();
  int count = 0;
  while (millis() - lastByte < MODBUS_TIMEOUT_MS) {
    if (RS485_SERIAL.available()) {
      rx[count++] = RS485_SERIAL.read();
      lastByte = millis();
      if (count >= rxMax) break;
    }
  }
  return count;
}

// ========== ต่อ CRC ท้าย frame ==========
void appendCRC(uint8_t *buf, int payloadLen)
{
  uint16_t crc = calculateCRC(buf, payloadLen);
  buf[payloadLen]     = (uint8_t)(crc & 0xFF);
  buf[payloadLen + 1] = (uint8_t)((crc >> 8) & 0xFF);
}

// =============================================================
// FC01: Read Coils
// Python: Bridge.call("read_coils", slave_id, address, quantity)
// คืนค่า: hex string ของ coil data bytes (เช่น "CD01") หรือ "" ถ้า timeout
// =============================================================
String read_coils(int slave_id, int address, int quantity)
{
  uint8_t tx[8];
  tx[0] = (uint8_t)slave_id;
  tx[1] = 0x01;
  tx[2] = (uint8_t)((address >> 8) & 0xFF);
  tx[3] = (uint8_t)(address & 0xFF);
  tx[4] = (uint8_t)((quantity >> 8) & 0xFF);
  tx[5] = (uint8_t)(quantity & 0xFF);
  appendCRC(tx, 6);

  uint8_t rx[RX_BUF_SIZE];
  int rxLen = sendAndReceive(tx, 8, rx, RX_BUF_SIZE);

  // Response: [slave][01][byteCount][data...][crc][crc]  min = 5 + byteCount
  if (rxLen >= 5 && rx[1] == 0x01) {
    int dataBytes = rx[2];
    String result = "";
    for (int i = 0; i < dataBytes && (3 + i) < rxLen; i++) {
      if (rx[3 + i] < 0x10) result += "0";
      result += String(rx[3 + i], HEX);
    }
    result.toUpperCase();
    return result;
  }
  return "";
}

// =============================================================
// FC02: Read Discrete Inputs
// Python: Bridge.call("read_discrete_inputs", slave_id, address, quantity)
// =============================================================
String read_discrete_inputs(int slave_id, int address, int quantity)
{
  uint8_t tx[8];
  tx[0] = (uint8_t)slave_id;
  tx[1] = 0x02;
  tx[2] = (uint8_t)((address >> 8) & 0xFF);
  tx[3] = (uint8_t)(address & 0xFF);
  tx[4] = (uint8_t)((quantity >> 8) & 0xFF);
  tx[5] = (uint8_t)(quantity & 0xFF);
  appendCRC(tx, 6);

  uint8_t rx[RX_BUF_SIZE];
  int rxLen = sendAndReceive(tx, 8, rx, RX_BUF_SIZE);

  if (rxLen >= 5 && rx[1] == 0x02) {
    int dataBytes = rx[2];
    String result = "";
    for (int i = 0; i < dataBytes && (3 + i) < rxLen; i++) {
      if (rx[3 + i] < 0x10) result += "0";
      result += String(rx[3 + i], HEX);
    }
    result.toUpperCase();
    return result;
  }
  return "";
}

// =============================================================
// FC03: Read Holding Registers
// Python: Bridge.call("read_holding_registers", slave_id, address, quantity)
// คืนค่า: hex string ของ register data (เช่น "006B0003") หรือ "" ถ้า timeout
// =============================================================
String read_holding_registers(int slave_id, int address, int quantity)
{
  uint8_t tx[8];
  tx[0] = (uint8_t)slave_id;
  tx[1] = 0x03;
  tx[2] = (uint8_t)((address >> 8) & 0xFF);
  tx[3] = (uint8_t)(address & 0xFF);
  tx[4] = (uint8_t)((quantity >> 8) & 0xFF);
  tx[5] = (uint8_t)(quantity & 0xFF);
  appendCRC(tx, 6);

  uint8_t rx[RX_BUF_SIZE];
  int rxLen = sendAndReceive(tx, 8, rx, RX_BUF_SIZE);

  if (rxLen >= 5 && rx[1] == 0x03) {
    int dataBytes = rx[2];
    String result = "";
    for (int i = 0; i < dataBytes && (3 + i) < rxLen; i++) {
      if (rx[3 + i] < 0x10) result += "0";
      result += String(rx[3 + i], HEX);
    }
    result.toUpperCase();
    return result;
  }
  return "";
}

// =============================================================
// FC04: Read Input Registers
// Python: Bridge.call("read_input_registers", slave_id, address, quantity)
// =============================================================
String read_input_registers(int slave_id, int address, int quantity)
{
  uint8_t tx[8];
  tx[0] = (uint8_t)slave_id;
  tx[1] = 0x04;
  tx[2] = (uint8_t)((address >> 8) & 0xFF);
  tx[3] = (uint8_t)(address & 0xFF);
  tx[4] = (uint8_t)((quantity >> 8) & 0xFF);
  tx[5] = (uint8_t)(quantity & 0xFF);
  appendCRC(tx, 6);

  uint8_t rx[RX_BUF_SIZE];
  int rxLen = sendAndReceive(tx, 8, rx, RX_BUF_SIZE);

  if (rxLen >= 5 && rx[1] == 0x04) {
    int dataBytes = rx[2];
    String result = "";
    for (int i = 0; i < dataBytes && (3 + i) < rxLen; i++) {
      if (rx[3 + i] < 0x10) result += "0";
      result += String(rx[3 + i], HEX);
    }
    result.toUpperCase();
    return result;
  }
  return "";
}

// =============================================================
// FC05: Write Single Coil
// Python: Bridge.call("write_coil", slave_id, address, value)
// value: 1=ON, 0=OFF   คืน: 1=สำเร็จ, 0=ล้มเหลว
// =============================================================
int write_coil(int slave_id, int address, int value)
{
  uint8_t tx[8];
  tx[0] = (uint8_t)slave_id;
  tx[1] = 0x05;
  tx[2] = (uint8_t)((address >> 8) & 0xFF);
  tx[3] = (uint8_t)(address & 0xFF);

  uint16_t mv = (value == 1) ? 0xFF00 : 0x0000;
  tx[4] = (uint8_t)((mv >> 8) & 0xFF);
  tx[5] = (uint8_t)(mv & 0xFF);
  appendCRC(tx, 6);

  uint8_t rx[RX_BUF_SIZE];
  int rxLen = sendAndReceive(tx, 8, rx, RX_BUF_SIZE);

  // FC05 echo: slave ตอบกลับ frame เดิมทั้ง 8 byte
  return (rxLen >= 8) ? 1 : 0;
}

// =============================================================
// FC06: Write Single Register
// Python: Bridge.call("write_register", slave_id, address, value)
// value: 0–65535   คืน: 1=สำเร็จ, 0=ล้มเหลว
// =============================================================
int write_register(int slave_id, int address, int value)
{
  uint8_t tx[8];
  tx[0] = (uint8_t)slave_id;
  tx[1] = 0x06;
  tx[2] = (uint8_t)((address >> 8) & 0xFF);
  tx[3] = (uint8_t)(address & 0xFF);
  tx[4] = (uint8_t)((value >> 8) & 0xFF);
  tx[5] = (uint8_t)(value & 0xFF);
  appendCRC(tx, 6);

  uint8_t rx[RX_BUF_SIZE];
  int rxLen = sendAndReceive(tx, 8, rx, RX_BUF_SIZE);

  // FC06 echo: slave ตอบกลับ frame เดิมทั้ง 8 byte
  return (rxLen >= 8) ? 1 : 0;
}

// =============================================================
// FC15 (0x0F): Write Multiple Coils
// Python: Bridge.call("write_coils", slave_id, address, quantity, hex_data)
// hex_data: hex string ของ coil bytes (เช่น "CD01")
// คืน: 1=สำเร็จ, 0=ล้มเหลว
// =============================================================
static uint8_t hexNibble(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return 0;
}

int write_coils(int slave_id, int address, int quantity, String hex_data)
{
  int dataByteCount = hex_data.length() / 2;
  int txLen = 7 + dataByteCount + 2; // header(7) + data + CRC(2)
  if (txLen > TX_BUF_SIZE) return 0;

  uint8_t tx[TX_BUF_SIZE];
  tx[0] = (uint8_t)slave_id;
  tx[1] = 0x0F;
  tx[2] = (uint8_t)((address >> 8) & 0xFF);
  tx[3] = (uint8_t)(address & 0xFF);
  tx[4] = (uint8_t)((quantity >> 8) & 0xFF);
  tx[5] = (uint8_t)(quantity & 0xFF);
  tx[6] = (uint8_t)dataByteCount;

  for (int i = 0; i < dataByteCount; i++) {
    tx[7 + i] = (hexNibble(hex_data[i * 2]) << 4) | hexNibble(hex_data[i * 2 + 1]);
  }
  appendCRC(tx, 7 + dataByteCount);

  uint8_t rx[RX_BUF_SIZE];
  int rxLen = sendAndReceive(tx, txLen, rx, RX_BUF_SIZE);

  // FC15 response: [slave][0F][addr_hi][addr_lo][qty_hi][qty_lo][crc][crc] = 8 bytes
  return (rxLen >= 8) ? 1 : 0;
}

// =============================================================
// FC16 (0x10): Write Multiple Registers
// Python: Bridge.call("write_registers", slave_id, address, quantity, hex_data)
// hex_data: hex string ของ register data (เช่น "000A0102")
// คืน: 1=สำเร็จ, 0=ล้มเหลว
// =============================================================
int write_registers(int slave_id, int address, int quantity, String hex_data)
{
  int dataByteCount = hex_data.length() / 2;
  int txLen = 7 + dataByteCount + 2;
  if (txLen > TX_BUF_SIZE) return 0;

  uint8_t tx[TX_BUF_SIZE];
  tx[0] = (uint8_t)slave_id;
  tx[1] = 0x10;
  tx[2] = (uint8_t)((address >> 8) & 0xFF);
  tx[3] = (uint8_t)(address & 0xFF);
  tx[4] = (uint8_t)((quantity >> 8) & 0xFF);
  tx[5] = (uint8_t)(quantity & 0xFF);
  tx[6] = (uint8_t)dataByteCount;

  for (int i = 0; i < dataByteCount; i++) {
    tx[7 + i] = (hexNibble(hex_data[i * 2]) << 4) | hexNibble(hex_data[i * 2 + 1]);
  }
  appendCRC(tx, 7 + dataByteCount);

  uint8_t rx[RX_BUF_SIZE];
  int rxLen = sendAndReceive(tx, txLen, rx, RX_BUF_SIZE);

  // FC16 response: [slave][10][addr_hi][addr_lo][qty_hi][qty_lo][crc][crc] = 8 bytes
  return (rxLen >= 8) ? 1 : 0;
}

// =============================================================
// Setup / Loop
// =============================================================
void setup()
{
  RS485_SERIAL.begin(RS485_BAUD);
  Bridge.begin();

  // ลงทะเบียน RPC ทั้ง 8 ฟังก์ชัน
  Bridge.provide("read_coils",             read_coils);              // FC01
  Bridge.provide("read_discrete_inputs",   read_discrete_inputs);    // FC02
  Bridge.provide("read_holding_registers", read_holding_registers);  // FC03
  Bridge.provide("read_input_registers",   read_input_registers);    // FC04
  Bridge.provide("write_coil",             write_coil);              // FC05
  Bridge.provide("write_register",         write_register);          // FC06
  Bridge.provide("write_coils",            write_coils);             // FC15
  Bridge.provide("write_registers",        write_registers);         // FC16
}

void loop()
{
}