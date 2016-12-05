// This file is Copyright (c) 2015 Florent Kermarrec <florent@enjoy-digital.fr>
// LiteETH lwIP port for ARTIQ
// License: BSD

#ifndef __ARCH_CC_H__
#define __ARCH_CC_H__

/* Include some files for defining library routines */
#define BYTE_ORDER BIG_ENDIAN

/* Compiler hints for packing structures */
#define PACK_STRUCT_FIELD(x) x
#define PACK_STRUCT_STRUCT __attribute__((packed))
#define PACK_STRUCT_BEGIN
#define PACK_STRUCT_END

/* prototypes for printf() and abort() */
#include <stdio.h>
#include <stdlib.h>
#include "console.h"
#define pp_printf printf

/* Definitions for ASSERT/DIAG */
#ifdef LWIP_NOASSERT
#define LWIP_PLATFORM_ASSERT(x)
#else
#define LWIP_PLATFORM_ASSERT(x) do {pp_printf("Assertion \"%s\" failed at line %d in %s\n", \
                                     x, __LINE__, __FILE__); } while(0)
#endif

#ifdef LWIP_DEBUG
#define LWIP_PLATFORM_DIAG(x)   do {pp_printf x;} while(0)
#endif

#endif /* __ARCH_CC_H__ */
