#ifndef __LOG_H
#define __LOG_H

#include <stdarg.h>

#define LOG_BUFFER_SIZE 4096

void core_log(const char *fmt, ...);
void core_log_va(const char *fmt, va_list args);
void core_log_get(char *outbuf);
void core_log_clear(void);

#endif /* __LOG_H */
