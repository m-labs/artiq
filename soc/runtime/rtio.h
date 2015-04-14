#ifndef __RTIO_H
#define __RTIO_H

void rtio_init(void);
void rtio_set_o(long long int timestamp, int channel, int value);
void rtio_set_oe(long long int timestamp, int channel, int oe);
void rtio_set_sensitivity(long long int timestamp, int channel, int sensitivity);
long long int rtio_get_counter(void);
long long int rtio_get(int channel, long long int time_limit);

void rtio_fud_sync(void);
void rtio_fud(long long int fud_time);

#endif /* __RTIO_H */
