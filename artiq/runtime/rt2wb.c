#include <generated/csr.h>

#include "artiq_personality.h"
#include "rtio.h"
#include "rt2wb.h"


void rt2wb_output(long long int timestamp, int channel, int addr,
        unsigned int data)
{
    rtio_output(timestamp, channel, addr, data);
}


unsigned int rt2wb_input(int channel)
{
    unsigned int data;
    int status;

    rtio_chan_sel_write(channel);
    while((status = rtio_i_status_read())) {
        if(status & RTIO_I_STATUS_OVERFLOW) {
            rtio_i_overflow_reset_write(1);
            artiq_raise_from_c("RTIOOverflow",
                    "RT2WB input overflow on channel {0}",
                    channel, 0, 0);
        }
    }

    data = rtio_i_data_read();
    rtio_i_re_write(1);
    return data;
}
