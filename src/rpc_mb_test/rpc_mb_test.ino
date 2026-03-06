
#include <Arduino.h>
#include <Arduino_RouterBridge.h>

#define RS485_SERIAL Serial
#define MODBUS_TIMEOUT_MS 200

uint16_t calculateCRC(uint8_t *buffer, int length) 
{
  uint16_t crc = 0xFFFF;
  for (int pos = 0; pos < length; pos++) {
    crc ^= (uint16_t)buffer[pos];
    for (int i = 8; i != 0; i--) {
      if ((crc & 0x0001) != 0) {
        crc >>= 1;
        crc ^= 0xA001;
      } else {
        crc >>= 1;
      }
    }
  }
  return crc;
}

int write_coil(int slave_id, int address, int value) 
{
  uint8_t tx_frame[8]; // เฟรมของ FC=05 จะมีขนาด 8 ไบต์เสมอ
  
  // 1. ประกอบเฟรมข้อมูล
  tx_frame[0] = (uint8_t)slave_id;
  tx_frame[1] = 0x05;                           // Function Code 05
  tx_frame[2] = (uint8_t)((address >> 8) & 0xFF); // Address High
  tx_frame[3] = (uint8_t)(address & 0xFF);        // Address Low
  
  // สเปค Modbus: สั่ง ON ให้ส่ง 0xFF00, สั่ง OFF ให้ส่ง 0x0000
  uint16_t modbus_val = (value == 1) ? 0xFF00 : 0x0000;
  tx_frame[4] = (uint8_t)((modbus_val >> 8) & 0xFF);
  tx_frame[5] = (uint8_t)(modbus_val & 0xFF);
  
  // 2. คำนวณ CRC และนำมาต่อท้าย (สลับเป็น Little Endian)
  uint16_t crc = calculateCRC(tx_frame, 6);
  tx_frame[6] = (uint8_t)(crc & 0xFF);        // CRC Low
  tx_frame[7] = (uint8_t)((crc >> 8) & 0xFF); // CRC High

  // 3. ยิงข้อมูลออก RS485
  for(int i = 0; i < 8; i++) {
    RS485_SERIAL.write(tx_frame[i]);
  }
  RS485_SERIAL.flush(); 

  // 4. รอรับข้อมูลตอบกลับ (Echo) จากตู้ยา
  unsigned long startTime = millis();
  int rx_count = 0;
  uint8_t rx_frame[16]; 

  while (millis() - startTime < MODBUS_TIMEOUT_MS) {
    if (RS485_SERIAL.available()) {
      delay(15); // หน่วงเวลาให้ข้อมูลมาครบเฟรม
      while (RS485_SERIAL.available() && rx_count < 16) {
        rx_frame[rx_count++] = RS485_SERIAL.read();
      }
      break; 
    }
  }

  // 5. แจ้งผลลัพธ์กลับไปที่ Python
  if (rx_count >= 8) 
  {
    return 1;
  }
  return 0;
}

void setup() 
{
  RS485_SERIAL.begin(9600); 

  Bridge.begin();        
  Bridge.provide("write_coil", write_coil); 
}

void loop ()
{

}