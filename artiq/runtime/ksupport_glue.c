#include <stdarg.h>
#include <string.h>
#include <stdio.h>
#include <math.h>

#include <link.h>
#include <dlfcn.h>

void send_to_log(const char *ptr, size_t length);

#define KERNELCPU_EXEC_ADDRESS    0x40400000
#define KERNELCPU_PAYLOAD_ADDRESS 0x40440000
#define KERNELCPU_LAST_ADDRESS    0x4fffffff
#define KSUPPORT_HEADER_SIZE      0x80

/* called by libunwind */
int fprintf(FILE *stream, const char *fmt, ...)
{
    size_t size;
    char *buf;
    va_list args;

    va_start(args, fmt);
    size = vsnprintf(NULL, 0, fmt, args);
    buf = __builtin_alloca(size + 1);
    va_end(args);

    va_start(args, fmt);
    vsnprintf(buf, size + 1, fmt, args);
    va_end(args);

    send_to_log(buf, size);
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
long lround(double x);
long lround(double x)
{
    return x < 0 ? floor(x) : ceil(x);
}

/* called by kernel */
int core_log(const char *fmt, ...);
int core_log(const char *fmt, ...)
{
    size_t size;
    char *buf;
    va_list args;

    va_start(args, fmt);
    size = vsnprintf(NULL, 0, fmt, args);
    buf = __builtin_alloca(size + 1);
    va_end(args);

    va_start(args, fmt);
    vsnprintf(buf, size + 1, fmt, args);
    va_end(args);

    send_to_log(buf, size);
    return 0;
}
