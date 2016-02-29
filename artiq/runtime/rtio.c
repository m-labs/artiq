#include <generated/csr.h>

#include "rtio.h"

void rtio_init(void)
{
    rtio_reset_write(1);
    rtio_reset_write(0);
    rtio_reset_phy_write(0);
}

long long int rtio_get_counter(void)
{
    rtio_counter_update_write(1);
    return rtio_counter_read();
}

void rtio_process_exceptional_status(int status, long long int timestamp, int channel)
{
    if(status & RTIO_O_STATUS_FULL)
        while(rtio_o_status_read() & RTIO_O_STATUS_FULL);
    if(status & RTIO_O_STATUS_UNDERFLOW) {
        rtio_o_underflow_reset_write(1);
        artiq_raise_from_c("RTIOUnderflow",
            "RTIO underflow at {0} mu, channel {1}, slack {2} mu",
            timestamp, channel, timestamp - rtio_get_counter());
    }
    if(status & RTIO_O_STATUS_SEQUENCE_ERROR) {
        rtio_o_sequence_error_reset_write(1);
        artiq_raise_from_c("RTIOSequenceError",
            "RTIO sequence error at {0} mu, channel {1}",
            timestamp, channel, 0);
    }
    if(status & RTIO_O_STATUS_COLLISION_ERROR) {
        rtio_o_collision_error_reset_write(1);
        artiq_raise_from_c("RTIOCollisionError",
            "RTIO collision error at {0} mu, channel {1}",
            timestamp, channel, 0);
    }
}


void rtio_output(long long int timestamp, int channel, unsigned int addr,
        unsigned int data)
{
    rtio_chan_sel_write(channel);
    rtio_o_timestamp_write(timestamp);
    rtio_o_address_write(addr);
    rtio_o_data_write(data);
    rtio_write_and_process_status(timestamp, channel);
}


int rtio_input_wait(long long int timeout, int channel)
{
    int status;

    rtio_chan_sel_write(channel);
    while((status = rtio_i_status_read())) {
        if(status & RTIO_I_STATUS_OVERFLOW) {
            rtio_i_overflow_reset_write(1);
            break;
        }
        if(rtio_get_counter() >= timeout) {
            /* check empty flag again to prevent race condition.
             * now we are sure that the time limit has been exceeded.
             */
            status = rtio_i_status_read();
            if(status & RTIO_I_STATUS_EMPTY)
                break;
        }
        /* input FIFO is empty - keep waiting */
    }
    return status;
}


void rtio_log_va(long long int timestamp, const char *fmt, va_list args)
{
    // This executes on the kernel CPU's stack, which is specifically designed
    // for allocation of this kind of massive buffers.
    int   len = vsnprintf(NULL, 0, fmt, args);
    char *buf = __builtin_alloca(len + 1);
    vsnprintf(buf, len + 1, fmt, args);

    rtio_chan_sel_write(CONFIG_RTIO_LOG_CHANNEL);
    rtio_o_timestamp_write(timestamp);

    int i = 0;
    unsigned int word = 0;
    while(1) {
        word <<= 8;
        word |= *buf & 0xff;
        if(*buf == 0) {
            rtio_o_data_write(word);
            rtio_o_we_write(1);
            break;
        }
        buf++;
        i++;
        if(i == 4) {
            rtio_o_data_write(word);
            rtio_o_we_write(1);
            word = 0;
            i = 0;
        }
    }
}

void rtio_log(long long int timestamp, const char *fmt, ...)
{
    va_list args;

    va_start(args, fmt);
    rtio_log_va(timestamp, fmt, args);
    va_end(args);
}
