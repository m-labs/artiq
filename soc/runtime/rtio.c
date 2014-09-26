#include <generated/csr.h>

#include "exceptions.h"
#include "rtio.h"

void rtio_init(void)
{
    rtio_reset_write(1);
}

void rtio_oe(int channel, int oe)
{
    rtio_chan_sel_write(channel);
    rtio_oe_write(oe);
}

void rtio_set(long long int timestamp, int channel, int value)
{
    rtio_reset_write(0);
    rtio_chan_sel_write(channel);
    rtio_o_timestamp_write(timestamp);
    rtio_o_value_write(value);
    while(!rtio_o_writable_read());
    rtio_o_we_write(1);
    if(rtio_o_error_read())
        exception_raise(EID_RTIO_UNDERFLOW);
}

void rtio_replace(long long int timestamp, int channel, int value)
{
    rtio_chan_sel_write(channel);
    rtio_o_timestamp_write(timestamp);
    rtio_o_value_write(value);
    rtio_o_replace_write(1);
    if(rtio_o_error_read())
        exception_raise(EID_RTIO_UNDERFLOW);
}

void rtio_sync(int channel)
{
    rtio_chan_sel_write(channel);
    while(rtio_o_level_read() != 0);
}

long long int rtio_get(int channel)
{
    long long int r;

    rtio_chan_sel_write(channel);
    while(rtio_i_readable_read() || (rtio_o_level_read() != 0)) {
        if(rtio_i_readable_read()) {
            r = rtio_i_value_read();
            rtio_i_re_write(1);
            return r;
        }
    }
    return -1;
}
