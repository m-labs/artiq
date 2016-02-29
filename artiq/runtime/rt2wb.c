#include <generated/csr.h>

#include "artiq_personality.h"
#include "rtio.h"
#include "rt2wb.h"


void rt2wb_write(long long int timestamp, int channel, int addr,
        unsigned int data)
{
    rtio_output(timestamp, channel, addr, data);
}


unsigned int rt2wb_read_sync(long long int timestamp, int channel, int addr,
        int duration)
{
    unsigned int data;
    rtio_output(timestamp, channel, addr, 0);
    rtio_input_wait(timestamp + duration, channel);
    data = rtio_i_data_read();
    rtio_i_re_write(1);
    return data;
}
