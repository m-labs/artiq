#include <string.h>

#include "elf_loader.h"
#include "corecom.h"
#include "gpio.h"
#include "rtio.h"
#include "dds.h"
#include "symbols.h"

static const struct symbol syscalls[] = {
    {"rpc", rpc},
    {"gpio_set", gpio_set},
    {"rtio_set", rtio_set},
    {"rtio_sync", rtio_sync},
    {"dds_program", dds_program},
    {NULL, NULL}
};

static long long int gcd64(long long int a, long long int b)
{
    long long int c;

    while(a) {
        c = a;
        a = b % a;
        b = c;
    }
    return b;
}

static const struct symbol arithmetic[] = {
    {"__gcd64", gcd64},
    {NULL, NULL}
};

void *resolve_symbol(const char *name)
{
    if(strncmp(name, "__syscall_", 10) == 0)
        return find_symbol(syscalls, name + 10);
    return find_symbol(arithmetic, name);
}
