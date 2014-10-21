#include <generated/csr.h>

#include "exceptions.h"
#include "rtio.h"

long long int previous_fud_end_time;

void rtio_init(void)
{
    previous_fud_end_time = 0;
    rtio_reset_counter_write(1);
    rtio_reset_logic_write(1);
    rtio_reset_logic_write(0);
}

void rtio_oe(int channel, int oe)
{
    rtio_chan_sel_write(channel);
    rtio_oe_write(oe);
}

void rtio_set(long long int timestamp, int channel, int value)
{
    rtio_reset_counter_write(0);
    rtio_chan_sel_write(channel);
    rtio_o_timestamp_write(timestamp);
    rtio_o_value_write(value);
    while(!rtio_o_writable_read());
    rtio_o_we_write(1);
    if(rtio_o_underflow_read()) {
        rtio_reset_logic_write(1);
        rtio_reset_logic_write(0);
        exception_raise(EID_RTIO_UNDERFLOW);
    }
}

void rtio_replace(long long int timestamp, int channel, int value)
{
    rtio_chan_sel_write(channel);
    rtio_o_timestamp_write(timestamp);
    rtio_o_value_write(value);
    rtio_o_replace_write(1);
    if(rtio_o_underflow_read()) {
        rtio_reset_logic_write(1);
        rtio_reset_logic_write(0);
        exception_raise(EID_RTIO_UNDERFLOW);
    }
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
        if(rtio_i_overflow_read()) {
            rtio_reset_logic_write(1);
            rtio_reset_logic_write(0);
            exception_raise(EID_RTIO_OVERFLOW);
        }
        if(rtio_i_readable_read()) {
            r = rtio_i_timestamp_read();
            rtio_i_re_write(1);
            return r;
        }
    }
    return -1;
}

int rtio_pileup_count(int channel)
{
    int r;

    rtio_chan_sel_write(channel);
    r = rtio_i_pileup_count_read();
    rtio_i_pileup_reset_write(1);
    return r;
}

#define RTIO_FUD_CHANNEL 4

void rtio_fud_sync(void)
{
    rtio_sync(RTIO_FUD_CHANNEL);
}

void rtio_fud(long long int fud_time)
{
    long long int fud_end_time;

    rtio_reset_counter_write(0);
    rtio_chan_sel_write(RTIO_FUD_CHANNEL);
    if(fud_time < 0) {
        rtio_counter_update_write(1);
        fud_time = rtio_counter_read() + 4000;
    }
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
    if(rtio_o_underflow_read()) {
        rtio_reset_logic_write(1);
        rtio_reset_logic_write(0);
        exception_raise(EID_RTIO_UNDERFLOW);
    }
}
