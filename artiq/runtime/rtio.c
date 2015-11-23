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
            "RTIO underflow at {0} mu, channel {1}, counter {2}",
            timestamp, channel, rtio_get_counter());
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
