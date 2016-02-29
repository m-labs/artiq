#include <generated/csr.h>

#include "artiq_personality.h"
#include "rtio.h"
#include "ttl.h"

void ttl_set_o(long long int timestamp, int channel, int value)
{
    rtio_output(timestamp, channel, 0, value);
}

void ttl_set_oe(long long int timestamp, int channel, int oe)
{
    rtio_output(timestamp, channel, 1, oe);
}

void ttl_set_sensitivity(long long int timestamp, int channel, int sensitivity)
{
    rtio_output(timestamp, channel, 2, sensitivity);
}

long long int ttl_get(int channel, long long int time_limit)
{
    long long int r;
    int status = rtio_input_wait(time_limit, channel);

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

void ttl_clock_set(long long int timestamp, int channel, int ftw)
{
    rtio_output(timestamp, channel, 0, ftw);
}
