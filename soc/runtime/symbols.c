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

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wimplicit-int"
extern __divsi3, __modsi3, __ledf2, __gedf2, __unorddf2, __negsf2, __negdf2,
    __addsf3, __subsf3, __mulsf3, __divsf3, __lshrdi3, __muldi3, __divdi3,
    __ashldi3, __ashrdi3, __udivmoddi4, __floatsisf, __floatunsisf, __fixsfsi,
    __fixunssfsi, __adddf3, __subdf3, __muldf3, __divdf3, __floatsidf,
    __floatunsidf, __floatdidf, __fixdfsi, __fixunsdfsi, __clzsi2, __ctzsi2,
    __udivdi3, __umoddi3, __moddi3;
#pragma GCC diagnostic pop

static const struct symbol arithmetic[] = {
    {"__divsi3", &__divsi3},
    {"__modsi3", &__modsi3},
    {"__ledf2", &__ledf2},
    {"__gedf2", &__gedf2},
    {"__unorddf2", &__gedf2},
    {"__negsf2", &__negsf2},
    {"__negdf2", &__negdf2},
    {"__addsf3", &__addsf3},
    {"__subsf3", &__subsf3},
    {"__mulsf3", &__mulsf3},
    {"__divsf3", &__divsf3},
    {"__lshrdi3", &__lshrdi3},
    {"__muldi3", &__muldi3},
    {"__divdi3", &__divdi3},
    {"__ashldi3", &__ashldi3},
    {"__ashrdi3", &__ashrdi3},
    {"__udivmoddi4", &__udivmoddi4},
    {"__floatsisf", &__floatsisf},
    {"__floatunsisf", &__floatunsisf},
    {"__fixsfsi", &__fixsfsi},
    {"__fixunssfsi", &__fixunssfsi},
    {"__adddf3", &__adddf3},
    {"__subdf3", &__subdf3},
    {"__muldf3", &__muldf3},
    {"__divdf3", &__divdf3},
    {"__floatsidf", &__floatsidf},
    {"__floatunsidf", &__floatunsidf},
    {"__floatdidf", &__floatdidf},
    {"__fixdfsi", &__fixdfsi},
    {"__fixunsdfsi", &__fixunsdfsi},
    {"__clzsi2", &__clzsi2},
    {"__ctzsi2", &__ctzsi2},
    {"__udivdi3", &__udivdi3},
    {"__umoddi3", &__umoddi3},
    {"__moddi3", &__moddi3},
    {"__gcd64", gcd64},
    {NULL, NULL}
};

void *resolve_symbol(const char *name)
{
    if(strncmp(name, "__syscall_", 10) == 0)
        return find_symbol(syscalls, name + 10);
    return find_symbol(arithmetic, name);
}
