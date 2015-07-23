#include <generated/csr.h>

#include "exceptions.h"
#include "rtio.h"
#include "ttl.h"

void ttl_set_o(long long int timestamp, int channel, int value)
{
    rtio_chan_sel_write(channel);
    rtio_o_timestamp_write(timestamp);
    rtio_o_address_write(0);
    rtio_o_data_write(value);
    rtio_write_and_process_status(timestamp, channel);
}

void ttl_set_oe(long long int timestamp, int channel, int oe)
{
    rtio_chan_sel_write(channel);
    rtio_o_timestamp_write(timestamp);
    rtio_o_address_write(1);
    rtio_o_data_write(oe);
    rtio_write_and_process_status(timestamp, channel);
}

void ttl_set_sensitivity(long long int timestamp, int channel, int sensitivity)
{
    rtio_chan_sel_write(channel);
    rtio_o_timestamp_write(timestamp);
    rtio_o_address_write(2);
    rtio_o_data_write(sensitivity);
    rtio_write_and_process_status(timestamp, channel);
}

long long int ttl_get(int channel, long long int time_limit)
{
    long long int r;
    int status;

    rtio_chan_sel_write(channel);
    while((status = rtio_i_status_read())) {
        if(rtio_i_status_read() & RTIO_I_STATUS_OVERFLOW) {
            rtio_i_overflow_reset_write(1);
            exception_raise_params(EID_RTIO_OVERFLOW,
                channel, 0, 0);
        }
        if(rtio_get_counter() >= time_limit) {
            /* check empty flag again to prevent race condition.
             * now we are sure that the time limit has been exceeded.
             */
            if(rtio_i_status_read() & RTIO_I_STATUS_EMPTY)
                return -1;
        }
        /* input FIFO is empty - keep waiting */
    }
    r = rtio_i_timestamp_read();
    rtio_i_re_write(1);
    return r;
}

void ttl_clock_set(long long int timestamp, int channel, int ftw)
{
    rtio_chan_sel_write(channel);
    rtio_o_timestamp_write(timestamp);
    rtio_o_data_write(ftw);
    rtio_write_and_process_status(timestamp, channel);
}
