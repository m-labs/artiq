#ifndef __RTIO_H
#define __RTIO_H

void rtio_init(void);
void rtio_oe(int channel, int oe);
void rtio_set(long long int timestamp, int channel, int value);
void rtio_replace(long long int timestamp, int channel, int value);
void rtio_sync(int channel);
long long int rtio_get(int channel);

#endif /* __RTIO_H */
