#include <generated/csr.h>

#include "exceptions.h"
#include "rtio.h"

#define RTIO_O_STATUS_FULL 1
#define RTIO_O_STATUS_UNDERFLOW 2
#define RTIO_I_STATUS_EMPTY 1
#define RTIO_I_STATUS_OVERFLOW 2

long long int previous_fud_end_time;

void rtio_init(void)
{
    previous_fud_end_time = 0;
    rtio_reset_write(1);
    rtio_reset_write(0);
}

void rtio_oe(int channel, int oe)
{
    rtio_chan_sel_write(channel);
    rtio_oe_write(oe);
}

void rtio_set(long long int timestamp, int channel, int value)
{
    int status;

    rtio_chan_sel_write(channel);
    rtio_o_timestamp_write(timestamp);
    rtio_o_value_write(value);
    rtio_o_we_write(1);
    status = rtio_o_status_read();
    if(status) {
        if(status & RTIO_O_STATUS_FULL)
            while(rtio_o_status_read() & RTIO_O_STATUS_FULL);
        if(status & RTIO_O_STATUS_UNDERFLOW) {
            rtio_o_underflow_reset_write(1);
            exception_raise(EID_RTIO_UNDERFLOW);
        }
    }
}

void rtio_replace(long long int timestamp, int channel, int value)
{
    rtio_chan_sel_write(channel);
    rtio_o_timestamp_write(timestamp);
    rtio_o_value_write(value);
    rtio_o_replace_write(1);
    if(rtio_o_status_read() & RTIO_O_STATUS_UNDERFLOW) {
        rtio_o_underflow_reset_write(1);
        exception_raise(EID_RTIO_UNDERFLOW);
    }
}

long long int rtio_get_counter(void)
{
    rtio_counter_update_write(1);
    return rtio_counter_read();
}

long long int rtio_get(int channel, long long int time_limit)
{
    long long int r;
    int status;

    rtio_chan_sel_write(channel);
    while(status = rtio_i_status_read()) {
        if(rtio_i_status_read() & RTIO_I_STATUS_OVERFLOW) {
            rtio_i_overflow_reset_write(1);
            exception_raise(EID_RTIO_OVERFLOW);
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

int rtio_pileup_count(int channel)
{
    int r;

    rtio_chan_sel_write(channel);
    r = rtio_i_pileup_count_read();
    rtio_i_pileup_reset_write(1);
    return r;
}

#define RTIO_FUD_CHANNEL 8

void rtio_fud_sync(void)
{
    while(rtio_get_counter() < previous_fud_end_time);
}

void rtio_fud(long long int fud_time)
{
    long long int fud_end_time;

    rtio_chan_sel_write(RTIO_FUD_CHANNEL);
    fud_end_time = fud_time + 3*8;
    if(fud_time < previous_fud_end_time)
        exception_raise(EID_RTIO_SEQUENCE_ERROR);
    previous_fud_end_time = fud_end_time;

    rtio_o_timestamp_write(fud_time);
    rtio_o_value_write(1);
    rtio_o_we_write(1);
    rtio_o_timestamp_write(fud_end_time);
    rtio_o_value_write(0);
    rtio_o_we_write(1);
    if(rtio_o_status_read() & RTIO_O_STATUS_UNDERFLOW) {
        rtio_o_underflow_reset_write(1);
        exception_raise(EID_RTIO_UNDERFLOW);
    }
}
