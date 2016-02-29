#ifndef __RT2WB_H
#define __RT2WB_H

void rt2wb_write(long long int timestamp, int channel, int address,
		unsigned int data);
unsigned int rt2wb_read_sync(long long int timestamp, int channel, int address,
		int duration);

#endif /* __RT2WB_H */

