#include <generated/csr.h>
#include <hw/common.h>
#include <stdio.h>

#include "rtio.h"
#include "dds.h"

#define DDS_FTW0  0x0a
#define DDS_FTW1  0x0b
#define DDS_FTW2  0x0c
#define DDS_FTW3  0x0d
#define DDS_POW0  0x0e
#define DDS_POW1  0x0f
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
        dds_phase_clear_en(i, 0);
    }
}

void dds_phase_clear_en(int channel, int phase_clear_en)
{
    DDS_WRITE(0x00, 0x78);
    DDS_WRITE(0x01, 0x00);
    DDS_WRITE(0x02, phase_clear_en ? 0x40 : 0x00);
    DDS_WRITE(0x03, 0x00);
}

/*
 * DDS phase modes:
 * - continuous: Set sysclk_per_microcycle=0 to disable POW alteration.
 *               phase_tracking is ignored, set to 0.
 *               Disable phase accumulator clearing prior to programming.
 * - absolute:   Set sysclk_per_microcycle to its nominal value
 *               and phase_tracking=0.
 *               Enable phase accumulator clearing prior to programming.
 * - tracking:   Set sysclk_per_microcycle to its nominal value
 *               and phase_tracking=1.
*                Enable phase accumulator clearing prior to programming.
 */
void dds_program(long long int timestamp, int channel,
    unsigned int ftw, unsigned int pow, unsigned int sysclk_per_microcycle,
    int rt_fud, int phase_tracking)
{
    long long int fud_time;
    unsigned int phase_time_offset;

    rtio_fud_sync();
    DDS_WRITE(DDS_GPIO, channel);

    DDS_WRITE(DDS_FTW0, ftw & 0xff);
    DDS_WRITE(DDS_FTW1, (ftw >> 8) & 0xff);
    DDS_WRITE(DDS_FTW2, (ftw >> 16) & 0xff);
    DDS_WRITE(DDS_FTW3, (ftw >> 24) & 0xff);

    phase_time_offset = phase_tracking ? timestamp : 0;
    if(rt_fud)
        fud_time = timestamp;
    else {
        fud_time = rtio_get_counter() + 8000;
        /* POW is mod 2**14, so wraparound on negative values is OK */
        phase_time_offset -= timestamp - fud_time;
    }
    pow += phase_time_offset*ftw*sysclk_per_microcycle >> 18;
    DDS_WRITE(DDS_POW0, pow & 0xff);
    DDS_WRITE(DDS_POW1, (pow >> 8) & 0x3f);

    rtio_fud(fud_time);
}
