#ifndef __RTIO_H
#define __RTIO_H

#include <generated/csr.h>
#include "artiq_personality.h"

#define RTIO_O_STATUS_FULL 1
#define RTIO_O_STATUS_UNDERFLOW 2
#define RTIO_O_STATUS_SEQUENCE_ERROR 4
#define RTIO_I_STATUS_EMPTY 1
#define RTIO_I_STATUS_OVERFLOW 2

void rtio_init(void);
long long int rtio_get_counter(void);

static inline void rtio_write_and_process_status(long long int timestamp, int channel)
{
    int status;

    rtio_o_we_write(1);
    status = rtio_o_status_read();
    if(status) {
        if(status & RTIO_O_STATUS_FULL)
            while(rtio_o_status_read() & RTIO_O_STATUS_FULL);
        if(status & RTIO_O_STATUS_UNDERFLOW) {
            rtio_o_underflow_reset_write(1);
            artiq_raise_from_c("RTIOUnderflow",
                "RTIO underflow at {0}mu, channel {1}, counter {2}",
                timestamp, channel, rtio_get_counter());
        }
        if(status & RTIO_O_STATUS_SEQUENCE_ERROR) {
            rtio_o_sequence_error_reset_write(1);
            artiq_raise_from_c("RTIOSequenceError",
                "RTIO sequence error at {0}mu, channel {1}",
                timestamp, channel, 0);
        }
    }
}

#endif /* __RTIO_H */
