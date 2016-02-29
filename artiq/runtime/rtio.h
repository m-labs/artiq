#ifndef __RTIO_H
#define __RTIO_H

#include <stdarg.h>
#include <generated/csr.h>
#include "artiq_personality.h"

#define RTIO_O_STATUS_FULL 1
#define RTIO_O_STATUS_UNDERFLOW 2
#define RTIO_O_STATUS_SEQUENCE_ERROR 4
#define RTIO_O_STATUS_COLLISION_ERROR 8
#define RTIO_I_STATUS_EMPTY 1
#define RTIO_I_STATUS_OVERFLOW 2

void rtio_init(void);
long long int rtio_get_counter(void);
void rtio_process_exceptional_status(int status, long long int timestamp, int channel);
void rtio_log(long long int timestamp, const char *format, ...);
void rtio_log_va(long long int timestamp, const char *format, va_list args);
void rtio_output(long long int timestamp, int channel, unsigned int address,
        unsigned int data);
void rtio_input_wait(long long int timeout, int channel);

static inline void rtio_write_and_process_status(long long int timestamp, int channel)
{
    int status;

    rtio_o_we_write(1);
    status = rtio_o_status_read();
    if(status)
        rtio_process_exceptional_status(status, timestamp, channel);
}

#endif /* __RTIO_H */
