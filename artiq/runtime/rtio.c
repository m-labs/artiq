#include <generated/csr.h>

#include "artiq_personality.h"
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

static void rtio_process_exceptional_status(
        long long int timestamp, int channel, int status)
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
    if(status & RTIO_O_STATUS_COLLISION) {
        rtio_o_collision_reset_write(1);
        artiq_raise_from_c("RTIOCollision",
            "RTIO collision at {0} mu, channel {1}",
            timestamp, channel, 0);
    }
    if(status & RTIO_O_STATUS_BUSY) {
        rtio_o_busy_reset_write(1);
        artiq_raise_from_c("RTIOBusy",
            "RTIO busy on channel {0}",
            channel, 0, 0);
    }
}


void rtio_output(long long int timestamp, int channel, unsigned int addr,
        unsigned int data)
{
    int status;

    rtio_chan_sel_write(channel);
    rtio_o_timestamp_write(timestamp);
#ifdef CSR_RTIO_O_ADDRESS_ADDR
    rtio_o_address_write(addr);
#endif
    rtio_o_data_write(data);
    rtio_o_we_write(1);
    status = rtio_o_status_read();
    if(status)
        rtio_process_exceptional_status(timestamp, channel, status);
}


long long int rtio_input_timestamp(long long int timeout, int channel)
{
    long long int r;
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

    if (status & RTIO_I_STATUS_OVERFLOW)
        artiq_raise_from_c("RTIOOverflow",
                "RTIO input overflow on channel {0}",
                channel, 0, 0);
    if (status & RTIO_I_STATUS_EMPTY)
        return -1;

    r = rtio_i_timestamp_read();
    rtio_i_re_write(1);
    return r;
}


unsigned int rtio_input_data(int channel)
{
    unsigned int data;
    int status;

    rtio_chan_sel_write(channel);
    while((status = rtio_i_status_read())) {
        if(status & RTIO_I_STATUS_OVERFLOW) {
            rtio_i_overflow_reset_write(1);
            artiq_raise_from_c("RTIOOverflow",
                    "RTIO input overflow on channel {0}",
                    channel, 0, 0);
        }
    }

    data = rtio_i_data_read();
    rtio_i_re_write(1);
    return data;
}


void rtio_log_va(long long int timestamp, const char *fmt, va_list args)
{
#ifdef CONFIG_RTIO_LOG_CHANNEL
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
#endif
}

void rtio_log(long long int timestamp, const char *fmt, ...)
{
    va_list args;

    va_start(args, fmt);
    rtio_log_va(timestamp, fmt, args);
    va_end(args);
}
