#ifndef __DDS_H
#define __DDS_H

#include <hw/common.h>

#define DDS_READ(addr) \
    MMPTR(0xb0000000 + (addr)*4)

#define DDS_WRITE(addr, data) \
    MMPTR(0xb0000000 + (addr)*4) = data

#define DDS_FTW0  0x0a
#define DDS_FTW1  0x0b
#define DDS_FTW2  0x0c
#define DDS_FTW3  0x0d
#define DDS_POW0  0x0e
#define DDS_POW1  0x0f
#define DDS_GPIO  0x41

void dds_init(void);
void dds_phase_clear_en(int channel, int phase_clear_en);
void dds_program(long long int timestamp, int channel,
    unsigned int ftw, unsigned int pow, unsigned int sysclk_per_microcycle,
    int rt_fud, int phase_tracking);

#endif /* __DDS_H */
