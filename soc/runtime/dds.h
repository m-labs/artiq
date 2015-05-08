#ifndef __DDS_H
#define __DDS_H

#include <hw/common.h>
#include <generated/mem.h>

/* Maximum number of commands in a batch */
#define DDS_MAX_BATCH 16

/* DDS core registers */
#define DDS_FTW0  0x0a
#define DDS_FTW1  0x0b
#define DDS_FTW2  0x0c
#define DDS_FTW3  0x0d
#define DDS_POW0  0x0e
#define DDS_POW1  0x0f
#define DDS_FUD   0x40
#define DDS_GPIO  0x41

enum {
    PHASE_MODE_CONTINUOUS = 0,
    PHASE_MODE_ABSOLUTE = 1,
    PHASE_MODE_TRACKING = 2
};

void dds_init(long long int timestamp, int channel);
void dds_batch_enter(long long int timestamp);
void dds_batch_exit(void);
void dds_set(long long int timestamp, int channel,
    unsigned int ftw, unsigned int pow, int phase_mode);

#endif /* __DDS_H */
