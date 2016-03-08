#ifndef __RTIO_H
#define __RTIO_H

#include <stdarg.h>
#include "generated/csr.h"

#define RTIO_O_STATUS_FULL 1
#define RTIO_O_STATUS_UNDERFLOW 2
#define RTIO_O_STATUS_SEQUENCE_ERROR 4
#define RTIO_O_STATUS_COLLISION 8
#define RTIO_O_STATUS_BUSY 16
#define RTIO_I_STATUS_EMPTY 1
#define RTIO_I_STATUS_OVERFLOW 2

void rtio_init(void);
long long int rtio_get_counter(void);
void rtio_log(long long int timestamp, const char *format, ...);
void rtio_log_va(long long int timestamp, const char *format, va_list args);
void rtio_output(long long int timestamp, int channel, unsigned int address,
        unsigned int data);

/*
 * Waits at least until timeout and returns the timestamp of the first
 * input event on the chanel, -1 if there was no event.
 */
long long int rtio_input_timestamp(long long int timeout, int channel);

/*
 * Assumes that there is or will be an event in the channel and returns only
 * its data.
 */
unsigned int rtio_input_data(int channel);

#endif /* __RTIO_H */
