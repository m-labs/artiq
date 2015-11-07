#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <console.h>

#include <generated/csr.h>

#include "log.h"

static int buffer_index;
static char buffer[LOG_BUFFER_SIZE];

void lognonl_va(const char *fmt, va_list args)
{
    char outbuf[256];
    int i, len;

    len = vscnprintf(outbuf, sizeof(outbuf), fmt, args);
    for(i=0;i<len;i++) {
        buffer[buffer_index] = outbuf[i];
        buffer_index = (buffer_index + 1) % LOG_BUFFER_SIZE;
    }

#ifdef CSR_ETHMAC_BASE
    /* Since main comms are over ethernet, the serial port
     * is free for us to use. */
    putsnonl(outbuf);
#endif
}

void lognonl(const char *fmt, ...)
{
    va_list args;

    va_start(args, fmt);
    lognonl_va(fmt, args);
    va_end(args);
}

void log_va(const char *fmt, va_list args)
{
    lognonl_va(fmt, args);
    lognonl("\n");
}

void log(const char *fmt, ...)
{
    va_list args;

    va_start(args, fmt);
    log_va(fmt, args);
    va_end(args);
}

void log_get(char *outbuf)
{
    int i, j;

    j = buffer_index;
    for(i = 0; i < LOG_BUFFER_SIZE; i++) {
        outbuf[i] = buffer[j];
        j = (j + 1) % LOG_BUFFER_SIZE;
    }
}

void log_clear()
{
    memset(buffer, 0, sizeof(buffer));
}
