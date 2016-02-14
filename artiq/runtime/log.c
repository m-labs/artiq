#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <console.h>

#include <generated/csr.h>

#include "log.h"

static int buffer_cursor;
static char buffer[LOG_BUFFER_SIZE];

void core_log(const char *fmt, ...)
{
    va_list args;

    va_start(args, fmt);
    core_log_va(fmt, args);
    va_end(args);
}

void core_log_va(const char *fmt, va_list args)
{
    char outbuf[256];
    int len = vscnprintf(outbuf, sizeof(outbuf), fmt, args);

    for(int i = 0; i < len; i++) {
        buffer[buffer_cursor] = outbuf[i];
        buffer_cursor = (buffer_cursor + 1) % LOG_BUFFER_SIZE;
    }

#ifdef CSR_ETHMAC_BASE
    /* Since main comms are over ethernet, the serial port
     * is free for us to use. */
    putsnonl(outbuf);
#endif
}

void core_log_get(char *outbuf)
{
    int j = buffer_cursor;
    for(int i = 0; i < LOG_BUFFER_SIZE; i++) {
        outbuf[i] = buffer[j];
        j = (j + 1) % LOG_BUFFER_SIZE;
    }
}

void core_log_clear()
{
    memset(buffer, 0, sizeof(buffer));
}
