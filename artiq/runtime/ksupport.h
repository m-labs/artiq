#ifndef __KSTARTUP_H
#define __KSTARTUP_H

struct artiq_list {
    int32_t length;
    int32_t *elements;
};

long long int now_init(void);
void now_save(long long int now);
int watchdog_set(int ms);
void watchdog_clear(int id);
void send_rpc(int service, const char *tag, ...);
int recv_rpc(void *slot);
struct artiq_list cache_get(const char *key);
void cache_put(const char *key, struct artiq_list value);
void core_log(const char *fmt, ...);

#endif /* __KSTARTUP_H */
