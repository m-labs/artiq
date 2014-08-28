#include <generated/csr.h>

#include "rtio.h"

void rtio_init(void)
{
	rtio_reset_write(1);
}

void rtio_set(long long int timestamp, int channel, int value)
{
	rtio_reset_write(0);
	rtio_chan_sel_write(channel);
	rtio_o_timestamp_write(timestamp);
	rtio_o_value_write(value);
	while(!rtio_o_writable_read());
	rtio_o_we_write(1);
}

void rtio_sync(int channel)
{
	rtio_chan_sel_write(channel);
	while(rtio_o_level_read() != 0);
}
