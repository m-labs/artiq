#ifndef __TTL_H
#define __TTL_H

void ttl_set_o(long long int timestamp, int channel, int value);
void ttl_set_oe(long long int timestamp, int channel, int oe);
void ttl_set_sensitivity(long long int timestamp, int channel, int sensitivity);
long long int ttl_get(int channel, long long int time_limit);
void ttl_clock_set(long long int timestamp, int channel, int ftw);

#endif /* __TTL_H */
