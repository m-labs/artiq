#include <generated/csr.h>

#include "artiq_personality.h"
#include "rtio.h"
#include "rt2wb.h"


void rt2wb_write(long long int timestamp, int channel, int addr,
        unsigned int data)
{
    rtio_chan_sel_write(channel);
    rtio_o_address_write(addr);
    rtio_o_data_write(data);
    rtio_o_timestamp_write(timestamp);
    rtio_write_and_process_status(timestamp, channel);
}


unsigned int rt2wb_read_sync(long long int timestamp, int channel,
        int addr, int duration)
{
    int status;
    unsigned int data;

    rt2wb_write(timestamp, channel, addr, 0);

    while((status = rtio_i_status_read())) {
        if(status & RTIO_I_STATUS_OVERFLOW) {
            rtio_i_overflow_reset_write(1);
            artiq_raise_from_c("RTIOOverflow",
                "RT2WB overflow on channel {0}",
                channel, 0, 0);
        }
        if(rtio_get_counter() >= timestamp + duration) {
            /* check empty flag again to prevent race condition.
             * now we are sure that the time limit has been exceeded.
             */
            if(rtio_i_status_read() & RTIO_I_STATUS_EMPTY)
                artiq_raise_from_c("InternalError",
                        "RT2WB read failed on channel {0}",
                        channel, 0, 0);
        }
        /* input FIFO is empty - keep waiting */
    }
    data = rtio_i_data_read();
    rtio_i_re_write(1);
    return data;
}
