#ifndef __RT2WB_H
#define __RT2WB_H

#include "rtio.h"

void rt2wb_output(long long int timestamp, int channel, int addr,
		unsigned int data);
unsigned int rt2wb_input(int channel);
unsigned int rt2wb_input_sync(long long int timeout, int channel);

#endif /* __RT2WB_H */

