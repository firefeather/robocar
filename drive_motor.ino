#include "car.h"
#include <SPI.h>
#include <RF24.h>


Car car;
RF24 radio(A0, 10);
const uint64_t pipes[2] = {0X0202020202LL, 0X0101010101LL};


void setup() 
{ 
    Serial.begin(115200);
    
    car.wheel_left.set_power(0);
    car.wheel_right.set_power(0);

    radio.begin();
    radio.setChannel(66);
    radio.setDataRate(RF24_2MBPS);
    radio.setAutoAck(true);
    radio.setCRCLength(RF24_CRC_8);
    radio.setRetries(15,15);
    radio.setPayloadSize(32);
    radio.openReadingPipe(0, pipes[0]);
    radio.openReadingPipe(1, pipes[1]);
    radio.startListening();
    radio.enableDynamicPayloads();
}

void loop() 
{
    car.update();
    //проверка данных
    if (radio.available())
    {
        uint8_t size = radio.getDynamicPayloadSize();
        uint8_t data[33];
        radio.read(data, size);
        car.process_command(&data[1], size);
    }
}
