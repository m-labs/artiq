#ifndef __KSTARTUP_H
#define __KSTARTUP_H

struct artiq_list {
    int32_t length;
    int32_t *elements;
};

int watchdog_set(int ms);
void watchdog_clear(int id);
void send_rpc(int service, const char *tag, void **data);
int recv_rpc(void *slot);
struct artiq_list cache_get(const char *key);
void cache_put(const char *key, struct artiq_list value);
void core_log(const char *fmt, ...);

#endif /* __KSTARTUP_H */
