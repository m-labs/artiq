#include <generated/csr.h>

#include "exceptions.h"
#include "rtio.h"

#define RTIO_O_STATUS_FULL 1
#define RTIO_O_STATUS_UNDERFLOW 2
#define RTIO_O_STATUS_SEQUENCE_ERROR 4
#define RTIO_I_STATUS_EMPTY 1
#define RTIO_I_STATUS_OVERFLOW 2

long long int previous_fud_end_time;

void rtio_init(void)
{
    previous_fud_end_time = 0;
    rtio_reset_write(1);
    rtio_reset_write(0);
    rtio_reset_phy_write(0);
}

static void write_and_process_status(long long int timestamp, int channel)
{
    int status;

    rtio_o_we_write(1);
    status = rtio_o_status_read();
    if(status) {
        if(status & RTIO_O_STATUS_FULL)
            while(rtio_o_status_read() & RTIO_O_STATUS_FULL);
        if(status & RTIO_O_STATUS_UNDERFLOW) {
            rtio_o_underflow_reset_write(1);
            exception_raise_params(EID_RTIO_UNDERFLOW,
                timestamp, channel, rtio_get_counter());
        }
        if(status & RTIO_O_STATUS_SEQUENCE_ERROR) {
            rtio_o_sequence_error_reset_write(1);
            exception_raise_params(EID_RTIO_SEQUENCE_ERROR,
                timestamp, channel, 0);
        }
    }
}

void rtio_set_o(long long int timestamp, int channel, int value)
{
    rtio_chan_sel_write(channel);
    rtio_o_timestamp_write(timestamp);
    rtio_o_address_write(0);
    rtio_o_data_write(value);
    write_and_process_status(timestamp, channel);
}

void rtio_set_oe(long long int timestamp, int channel, int oe)
{
    rtio_chan_sel_write(channel);
    rtio_o_timestamp_write(timestamp);
    rtio_o_address_write(1);
    rtio_o_data_write(oe);
    write_and_process_status(timestamp, channel);
}

void rtio_set_sensitivity(long long int timestamp, int channel, int sensitivity)
{
    rtio_chan_sel_write(channel);
    rtio_o_timestamp_write(timestamp);
    rtio_o_address_write(2);
    rtio_o_data_write(sensitivity);
    write_and_process_status(timestamp, channel);
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

void rtio_fud_sync(void)
{
    while(rtio_get_counter() < previous_fud_end_time);
}

void rtio_fud(long long int fud_time)
{
    long long int fud_end_time;
    int status;

    rtio_chan_sel_write(RTIO_FUD_CHANNEL);
    rtio_o_address_write(0);
    fud_end_time = fud_time + 3*8;
    previous_fud_end_time = fud_end_time;

    rtio_o_timestamp_write(fud_time);
    rtio_o_data_write(1);
    rtio_o_we_write(1);
    rtio_o_timestamp_write(fud_end_time);
    rtio_o_data_write(0);
    rtio_o_we_write(1);
    status = rtio_o_status_read();
    if(status) {
        if(status & RTIO_O_STATUS_UNDERFLOW) {
            rtio_o_underflow_reset_write(1);
            exception_raise_params(EID_RTIO_UNDERFLOW,
                fud_time, RTIO_FUD_CHANNEL, rtio_get_counter());
        }
        if(status & RTIO_O_STATUS_SEQUENCE_ERROR) {
            rtio_o_sequence_error_reset_write(1);
            exception_raise_params(EID_RTIO_SEQUENCE_ERROR,
                fud_time, RTIO_FUD_CHANNEL, 0);
        }
    }
}
