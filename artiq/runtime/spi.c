#include <generated/csr.h>
#include <stdio.h>

#include "artiq_personality.h"
#include "rtio.h"
#include "log.h"
#include "spi.h"


#define DURATION_WRITE (1 << CONFIG_RTIO_FINE_TS_WIDTH)

void spi_write(long long int timestamp, int channel, int addr,
        unsigned int data)
{
    rtio_chan_sel_write(CONFIG_RTIO_FIRST_SPI_CHANNEL + channel);
    rtio_o_address_write(addr);
    rtio_o_data_write(data);
    rtio_o_timestamp_write(timestamp);
    rtio_write_and_process_status(timestamp, channel);
}


unsigned int spi_read(long long int timestamp, int channel, int addr)
{
    int status;
    long long int time_limit = timestamp + DURATION_WRITE;
    unsigned int r;

    spi_write(timestamp, channel, addr | SPI_WB_READ, 0);

    while((status = rtio_i_status_read())) {
        if(rtio_i_status_read() & RTIO_I_STATUS_OVERFLOW) {
            rtio_i_overflow_reset_write(1);
            artiq_raise_from_c("RTIOOverflow",
                "RTIO overflow at channel {0}",
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
    r = rtio_i_data_read();
    rtio_i_re_write(1);
    return r;
}
