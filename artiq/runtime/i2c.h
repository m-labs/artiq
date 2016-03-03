#ifndef __I2C_H
#define __I2C_H

int i2c_init(int busno);
void i2c_start(int busno);
void i2c_stop(int busno);
int i2c_write(int busno, char b);
char i2c_read(int busno, int ack);

#endif
