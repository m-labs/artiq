#include <stdarg.h>
#include <string.h>
#include <stdio.h>
#include <math.h>

#include <link.h>
#include <dlfcn.h>

struct slice {
    void   *ptr;
    size_t  len;
};

void send_to_core_log(struct slice str);
void send_to_rtio_log(struct slice data);

#define KERNELCPU_EXEC_ADDRESS    0x40800000
#define KERNELCPU_PAYLOAD_ADDRESS 0x40840000
#define KERNELCPU_LAST_ADDRESS    0x4fffffff
#define KSUPPORT_HEADER_SIZE      0x80

FILE *stderr;

/* called by libunwind */
char *getenv(const char *var)
{
    return NULL;
}

/* called by libunwind */
int fprintf(FILE *stream, const char *fmt, ...)
{
    va_list args;

    va_start(args, fmt);
    size_t size = vsnprintf(NULL, 0, fmt, args);
    char *buf = __builtin_alloca(size + 1);
    va_end(args);

    va_start(args, fmt);
    vsnprintf(buf, size + 1, fmt, args);
    va_end(args);

    struct slice str = { buf, size };
    send_to_core_log(str);
    return 0;
}

/* called by libunwind */
int fflush(FILE *stream)
{
    return 0;
}

/* called by libunwind */
int dladdr (const void *address, Dl_info *info)
{
    /* we don't try to resolve names */
    return 0;
}

/* called by libunwind */
int dl_iterate_phdr (int (*callback)(struct dl_phdr_info *, size_t, void *), void *data)
{
    Elf32_Ehdr *ehdr;
    struct dl_phdr_info phdr_info;
    int retval;

    ehdr = (Elf32_Ehdr *)(KERNELCPU_EXEC_ADDRESS - KSUPPORT_HEADER_SIZE);
    phdr_info = (struct dl_phdr_info){
        .dlpi_addr  = 0, /* absolutely linked */
        .dlpi_name  = "<ksupport>",
        .dlpi_phdr  = (Elf32_Phdr*) ((intptr_t)ehdr + ehdr->e_phoff),
        .dlpi_phnum = ehdr->e_phnum,
    };
    retval = callback(&phdr_info, sizeof(phdr_info), data);
    if(retval)
        return retval;

    ehdr = (Elf32_Ehdr *)KERNELCPU_PAYLOAD_ADDRESS;
    phdr_info = (struct dl_phdr_info){
        .dlpi_addr  = KERNELCPU_PAYLOAD_ADDRESS,
        .dlpi_name  = "<kernel>",
        .dlpi_phdr  = (Elf32_Phdr*) ((intptr_t)ehdr + ehdr->e_phoff),
        .dlpi_phnum = ehdr->e_phnum,
    };
    retval = callback(&phdr_info, sizeof(phdr_info), data);
    return retval;
}

/* called by kernel */
double round(double x);
double round(double x)
{
    union {double f; uint64_t i;} u = {x};
    int e = u.i >> 52 & 0x7ff;
    double y;

    if (e >= 0x3ff+52)
        return x;
    if (u.i >> 63)
        x = -x;
    if (e < 0x3ff-1) {
        /* we don't do it in ARTIQ */
        /* raise inexact if x!=0 */
        // FORCE_EVAL(x + 0x1p52);
        return 0*u.f;
    }
    y = (double)(x + 0x1p52) - 0x1p52 - x;
    if (y > 0.5)
        y = y + x - 1;
    else if (y <= -0.5)
        y = y + x + 1;
    else
        y = y + x;
    if (u.i >> 63)
        y = -y;
    return y;
}

/* called by kernel */
int core_log(const char *fmt, ...);
int core_log(const char *fmt, ...)
{
    va_list args;

    va_start(args, fmt);
    size_t size = vsnprintf(NULL, 0, fmt, args);
    char *buf = __builtin_alloca(size + 1);
    va_end(args);

    va_start(args, fmt);
    vsnprintf(buf, size + 1, fmt, args);
    va_end(args);

    struct slice str = { buf, size };
    send_to_core_log(str);
    return 0;
}

/* called by kernel */
void rtio_log(const char *fmt, ...);
void rtio_log(const char *fmt, ...)
{
    va_list args;

    va_start(args, fmt);
    size_t size = vsnprintf(NULL, 0, fmt, args);
    char *buf = __builtin_alloca(size + 1);
    va_end(args);

    va_start(args, fmt);
    vsnprintf(buf, size + 1, fmt, args);
    va_end(args);

    struct slice str = { buf, size };
    send_to_rtio_log(str);
}
