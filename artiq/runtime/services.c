#include <string.h>

#include "elf_loader.h"
#include "session.h"
#include "clock.h"
#include "ttl.h"
#include "dds.h"
#include "exceptions.h"
#include "services.h"

#include "service_table.h"

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wimplicit-int"
extern __divsi3, __modsi3, __ledf2, __gedf2, __unorddf2, __eqdf2, __ltdf2,
    __nedf2, __gtdf2, __negsf2, __negdf2, __addsf3, __subsf3, __mulsf3,
    __divsf3, __lshrdi3, __muldi3, __divdi3, __ashldi3, __ashrdi3,
    __udivmoddi4, __floatsisf, __floatunsisf, __fixsfsi, __fixunssfsi,
    __adddf3, __subdf3, __muldf3, __divdf3, __floatsidf, __floatunsidf,
    __floatdidf, __fixdfsi, __fixdfdi, __fixunsdfsi, __clzsi2, __ctzsi2,
    __udivdi3, __umoddi3, __moddi3;
#pragma GCC diagnostic pop

static const struct symbol compiler_rt[] = {
    {"divsi3", &__divsi3},
    {"modsi3", &__modsi3},
    {"ledf2", &__ledf2},
    {"gedf2", &__gedf2},
    {"unorddf2", &__unorddf2},
    {"eqdf2", &__eqdf2},
    {"ltdf2", &__ltdf2},
    {"nedf2", &__nedf2},
    {"gtdf2", &__gtdf2},
    {"negsf2", &__negsf2},
    {"negdf2", &__negdf2},
    {"addsf3", &__addsf3},
    {"subsf3", &__subsf3},
    {"mulsf3", &__mulsf3},
    {"divsf3", &__divsf3},
    {"lshrdi3", &__lshrdi3},
    {"muldi3", &__muldi3},
    {"divdi3", &__divdi3},
    {"ashldi3", &__ashldi3},
    {"ashrdi3", &__ashrdi3},
    {"udivmoddi4", &__udivmoddi4},
    {"floatsisf", &__floatsisf},
    {"floatunsisf", &__floatunsisf},
    {"fixsfsi", &__fixsfsi},
    {"fixunssfsi", &__fixunssfsi},
    {"adddf3", &__adddf3},
    {"subdf3", &__subdf3},
    {"muldf3", &__muldf3},
    {"divdf3", &__divdf3},
    {"floatsidf", &__floatsidf},
    {"floatunsidf", &__floatunsidf},
    {"floatdidf", &__floatdidf},
    {"fixdfsi", &__fixdfsi},
    {"fixdfdi", &__fixdfdi},
    {"fixunsdfsi", &__fixunsdfsi},
    {"clzsi2", &__clzsi2},
    {"ctzsi2", &__ctzsi2},
    {"udivdi3", &__udivdi3},
    {"umoddi3", &__umoddi3},
    {"moddi3", &__moddi3},
    {NULL, NULL}
};

void *resolve_service_symbol(const char *name)
{
    if(strncmp(name, "__", 2) != 0)
        return NULL;
    name += 2;
    if(strncmp(name, "syscall_", 8) == 0)
        return find_symbol(syscalls, name + 8);
    if(strncmp(name, "eh_", 3) == 0)
        return find_symbol(eh, name + 3);
    return find_symbol(compiler_rt, name);
}
