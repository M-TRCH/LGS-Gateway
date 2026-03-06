
#include <Arduino_RouterBridge.h>

int test()
{
  return random(0,100); 
}

void setup() 
{
  Serial.begin(115200);

  Bridge.begin();   
  Bridge.provide("test", test);
}

void loop() 
{

}