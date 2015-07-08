#ifndef __DDS_H
#define __DDS_H

#include <hw/common.h>
#include <generated/csr.h>
#include <generated/mem.h>

/* Maximum number of commands in a batch */
#define DDS_MAX_BATCH 16

#ifdef DDS_AD9858
#define DDS_CFR0  0x00
#define DDS_CFR1  0x01
#define DDS_CFR2  0x02
#define DDS_CFR3  0x03
#define DDS_FTW0  0x0a
#define DDS_FTW1  0x0b
#define DDS_FTW2  0x0c
#define DDS_FTW3  0x0d
#define DDS_POW0  0x0e
#define DDS_POW1  0x0f
#define DDS_FUD   0x40
#define DDS_GPIO  0x41
#endif

#ifdef DDS_AD9914
#define DDS_CFR1L  0x01
#define DDS_CFR1H  0x03
#define DDS_CFR2L  0x05
#define DDS_CFR2H  0x07
#define DDS_CFR3L  0x09
#define DDS_CFR3H  0x0b
#define DDS_CFR4L  0x0d
#define DDS_CFR4H  0x0f
#define DDS_FTWL   0x2d
#define DDS_FTWH   0x2f
#define DDS_POW    0x31
#define DDS_FUD    0x80
#define DDS_GPIO   0x81
#endif

#ifdef DDS_AD9858
#define DDS_POW_WIDTH 14
#endif

#ifdef DDS_AD9914
#define DDS_POW_WIDTH 16
#endif

enum {
    PHASE_MODE_CONTINUOUS = 0,
    PHASE_MODE_ABSOLUTE = 1,
    PHASE_MODE_TRACKING = 2
};

void dds_init_all(void);
void dds_init(long long int timestamp, int channel);
void dds_batch_enter(long long int timestamp);
void dds_batch_exit(void);
void dds_set(long long int timestamp, int channel,
    unsigned int ftw, unsigned int pow, int phase_mode);

#endif /* __DDS_H */
