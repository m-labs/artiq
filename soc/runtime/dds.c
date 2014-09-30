#include <generated/csr.h>
#include <hw/common.h>
#include <stdio.h>

#include "exceptions.h"
#include "dds.h"

#define DDS_FTW0  0x0a
#define DDS_FTW1  0x0b
#define DDS_FTW2  0x0c
#define DDS_FTW3  0x0d
#define DDS_GPIO  0x41

#define DDS_READ(addr) \
    MMPTR(0xb0000000 + (addr)*4)

#define DDS_WRITE(addr, data) \
    MMPTR(0xb0000000 + (addr)*4) = data

#define RTIO_FUD_CHANNEL 4

static void fud_sync(void)
{
    rtio_chan_sel_write(RTIO_FUD_CHANNEL);
    while(rtio_o_level_read() != 0);
}

static void fud(long long int fud_time)
{
    int r;
    static int previous_fud_time;

    r = rtio_reset_read();
    if(r)
        previous_fud_time = 0;
    rtio_reset_write(0);

    rtio_chan_sel_write(RTIO_FUD_CHANNEL);
    if(fud_time < 0) {
        rtio_counter_update_write(1);
        fud_time = rtio_counter_read() + 3000;
    }
    if(fud_time < previous_fud_time)
        exception_raise(EID_RTIO_SEQUENCE_ERROR);

    rtio_o_timestamp_write(fud_time);
    rtio_o_value_write(1);
    rtio_o_we_write(1);
    rtio_o_timestamp_write(fud_time+3*8);
    rtio_o_value_write(0);
    rtio_o_we_write(1);
    if(rtio_o_error_read())
        exception_raise(EID_RTIO_UNDERFLOW);

    if(r) {
        fud_sync();
        rtio_reset_write(1);
    }
}

void dds_init(void)
{
    int i;

    for(i=0;i<8;i++) {
        DDS_WRITE(DDS_GPIO, i | (1 << 7));
        DDS_WRITE(DDS_GPIO, i);
        DDS_WRITE(0x00, 0x78);
        DDS_WRITE(0x01, 0x00);
        DDS_WRITE(0x02, 0x00);
        DDS_WRITE(0x03, 0x00);
        fud(-1);
        fud_sync();
    }
}

void dds_program(int channel, int ftw, long long int fud_time)
{
    fud_sync();
    DDS_WRITE(DDS_GPIO, channel);
    DDS_WRITE(DDS_FTW0, ftw & 0xff);
    DDS_WRITE(DDS_FTW1, (ftw >> 8) & 0xff);
    DDS_WRITE(DDS_FTW2, (ftw >> 16) & 0xff);
    DDS_WRITE(DDS_FTW3, (ftw >> 24) & 0xff);
    fud(fud_time);
}
