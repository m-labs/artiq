#ifndef __CLOCK_H
#define __CLOCK_H

void clock_init(void);
long long int clock_get_ms(void);
void busywait_us(long long us);

#define MAX_WATCHDOGS 16

void watchdog_init(void);
int watchdog_set(int ms);
void watchdog_clear(int id);
int watchdog_expired(void);

#endif /* __CLOCK_H */
