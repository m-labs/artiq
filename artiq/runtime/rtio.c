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

void rtio_log(long long int timestamp, char *message)
{
    unsigned int word;
    int i;

    rtio_chan_sel_write(CONFIG_RTIO_LOG_CHANNEL);
    rtio_o_timestamp_write(timestamp);

    i = 0;
    word = 0;
    while(1) {
        word <<= 8;
        word |= *message & 0xff;
        if(*message == 0) {
            rtio_o_data_write(word);
            rtio_o_we_write(1);
            break;
        }
        message++;
        i++;
        if(i == 4) {
            rtio_o_data_write(word);
            rtio_o_we_write(1);
            word = 0;
            i = 0;
        }
    }
}
