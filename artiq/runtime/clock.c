#include <generated/csr.h>

#include "log.h"
#include "clock.h"


void clock_init(void)
{
    timer0_en_write(0);
    timer0_load_write(0x7fffffffffffffffLL);
    timer0_reload_write(0x7fffffffffffffffLL);
    timer0_en_write(1);
}

long long int clock_get_ms(void)
{
    long long int clock_sys;
    long long int clock_ms;

    timer0_update_value_write(1);
    clock_sys = 0x7fffffffffffffffLL - timer0_value_read();

    clock_ms = clock_sys/(SYSTEM_CLOCK_FREQUENCY/1000);
    return clock_ms;
}

void busywait_us(long long int us)
{
    long long int threshold;

    timer0_update_value_write(1);
    threshold = timer0_value_read() - us*SYSTEM_CLOCK_FREQUENCY/1000000LL;
    while(timer0_value_read() > threshold)
        timer0_update_value_write(1);
}

struct watchdog {
    int active;
    long long int threshold;
};

static struct watchdog watchdogs[MAX_WATCHDOGS];

void watchdog_init(void)
{
    int i;

    for(i=0;i<MAX_WATCHDOGS;i++)
        watchdogs[i].active = 0;
}

int watchdog_set(int ms)
{
    int i, id;

    id = -1;
    for(i=0;i<MAX_WATCHDOGS;i++)
        if(!watchdogs[i].active) {
            id = i;
            break;
        }
    if(id < 0) {
        log("WARNING: Failed to add watchdog");
        return id;
    }

    watchdogs[id].active = 1;
    watchdogs[id].threshold = clock_get_ms() + ms;
    return id;
}

void watchdog_clear(int id)
{
    if((id < 0) || (id >= MAX_WATCHDOGS))
        return;
    watchdogs[id].active = 0;
}

int watchdog_expired(void)
{
    int i;
    long long int t;

    t = 0x7fffffffffffffffLL;
    for(i=0;i<MAX_WATCHDOGS;i++)
        if(watchdogs[i].active && (watchdogs[i].threshold < t))
            t = watchdogs[i].threshold;
    return clock_get_ms() > t;
}
