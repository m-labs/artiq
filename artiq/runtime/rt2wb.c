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
    int status;

    rtio_output(timestamp, channel, addr, 0);

    status = rtio_input_wait(timestamp + duration, channel);
    if (status & RTIO_I_STATUS_OVERFLOW)
        artiq_raise_from_c("RTIOOverflow",
                "RT2WB read overflow on channel {0}",
                channel, 0, 0);
    if (status & RTIO_I_STATUS_EMPTY)
        artiq_raise_from_c("RTIOTimeout",
                "RT2WB read timeout on channel {0}",
                channel, 0, 0);

    data = rtio_i_data_read();
    rtio_i_re_write(1);
    return data;
}
