#include <generated/csr.h>
#include <stdio.h>

#include "rtio.h"
#include "dds.h"

#define DURATION_WRITE 5
#define DURATION_PROGRAM (8*DURATION_WRITE)

#define DDS_WRITE(addr, data) do { \
        rtio_o_address_write(addr); \
        rtio_o_data_write(data); \
        rtio_o_timestamp_write(now); \
        rtio_write_and_process_status(now, RTIO_DDS_CHANNEL); \
        now += DURATION_WRITE; \
    } while(0)

void dds_init(long long int timestamp, int channel)
{
    long long int now;

    rtio_chan_sel_write(RTIO_DDS_CHANNEL);

    now = timestamp - 7*DURATION_WRITE;

    DDS_WRITE(DDS_GPIO, channel);
    DDS_WRITE(DDS_GPIO, channel | (1 << 7));
    DDS_WRITE(DDS_GPIO, channel);

    DDS_WRITE(0x00, 0x78);
    DDS_WRITE(0x01, 0x00);
    DDS_WRITE(0x02, 0x00);
    DDS_WRITE(0x03, 0x00);
}

static void dds_set_one(long long int now, long long int timestamp, int channel,
    unsigned int ftw, unsigned int pow, int phase_mode)
{
    DDS_WRITE(DDS_GPIO, channel);

    if(phase_mode == PHASE_MODE_CONTINUOUS)
        /* Do not clear phase accumulator on FUD */
        DDS_WRITE(0x02, 0x00);
    else
        /* Clear phase accumulator on FUD */
        DDS_WRITE(0x02, 0x40);

    DDS_WRITE(DDS_FTW0, ftw & 0xff);
    DDS_WRITE(DDS_FTW1, (ftw >> 8) & 0xff);
    DDS_WRITE(DDS_FTW2, (ftw >> 16) & 0xff);
    DDS_WRITE(DDS_FTW3, (ftw >> 24) & 0xff);

    if(phase_mode == PHASE_MODE_TRACKING)
        /* We assume that the RTIO clock is DDS SYNCLK */
        pow += (timestamp >> RTIO_FINE_TS_WIDTH)*ftw >> 18;
    DDS_WRITE(DDS_POW0, pow & 0xff);
    DDS_WRITE(DDS_POW1, (pow >> 8) & 0x3f);
}

void dds_set(long long int timestamp, int channel,
    unsigned int ftw, unsigned int pow, int phase_mode)
{
    long long int now;

    rtio_chan_sel_write(RTIO_DDS_CHANNEL);
    dds_set_one(timestamp - DURATION_PROGRAM, timestamp, channel, ftw, pow, phase_mode);
    now = timestamp;
    DDS_WRITE(DDS_FUD, 0);
}
