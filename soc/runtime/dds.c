#include <generated/csr.h>
#include <hw/common.h>
#include <stdio.h>

#include "rtio.h"
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

void dds_init(void)
{
    int i;

    for(i=0;i<8;i++) {
        DDS_WRITE(DDS_GPIO, i);
        DDS_WRITE(DDS_GPIO, i | (1 << 7));
        DDS_WRITE(DDS_GPIO, i);
        DDS_WRITE(0x00, 0x78);
        DDS_WRITE(0x01, 0x00);
        DDS_WRITE(0x02, 0x00);
        DDS_WRITE(0x03, 0x00);
        rtio_fud(-1);
        rtio_fud_sync();
    }
}

void dds_program(int channel, int ftw, long long int fud_time)
{
    rtio_fud_sync();
    DDS_WRITE(DDS_GPIO, channel);
    DDS_WRITE(DDS_FTW0, ftw & 0xff);
    DDS_WRITE(DDS_FTW1, (ftw >> 8) & 0xff);
    DDS_WRITE(DDS_FTW2, (ftw >> 16) & 0xff);
    DDS_WRITE(DDS_FTW3, (ftw >> 24) & 0xff);
    rtio_fud(fud_time);
}
