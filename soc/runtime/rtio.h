#ifndef __RTIO_H
#define __RTIO_H

void rtio_init(void);
void rtio_set(long long int timestamp, int channel, int value);
void rtio_replace(long long int timestamp, int channel, int value);
void rtio_sync(int channel);

#endif /* __RTIO_H */
