#ifndef __ARTIQ_PERSONALITY_H
#define __ARTIQ_PERSONALITY_H

#include <stdint.h>
#include <stddef.h>

struct slice {
    void   *ptr;
    size_t  len;
};

struct artiq_exception {
  struct slice name;
  struct slice file;
  int32_t      line;
  int32_t      column;
  struct slice function;
  struct slice message;
  int64_t      param[3];
};

#ifdef __cplusplus
extern "C" {
#endif

/* Provided by the runtime */
void __artiq_raise(struct artiq_exception *artiq_exn)
        __attribute__((noreturn));
void __artiq_reraise(void)
        __attribute__((noreturn));

/* Called by the runtime */
void __artiq_terminate(struct artiq_exception *artiq_exn,
                       struct slice backtrace)
        __attribute__((noreturn));

#ifdef __cplusplus
}
#endif

#endif /* __ARTIQ_PERSONALITY_H */
