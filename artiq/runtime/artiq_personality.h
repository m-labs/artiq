#ifndef __ARTIQ_PERSONALITY_H
#define __ARTIQ_PERSONALITY_H

#include <stdint.h>
#include <stddef.h>

struct artiq_exception {
  union {
    uintptr_t typeinfo;
    const char *name;
  };
  const char *file;
  int32_t line;
  int32_t column;
  const char *function;
  const char *message;
  int64_t param[3];
};

struct artiq_backtrace_item {
  intptr_t function;
  intptr_t offset;
};

#ifdef __cplusplus
extern "C" {
#endif

/* Provided by the runtime */
void __artiq_raise(struct artiq_exception *artiq_exn)
        __attribute__((noreturn));
void __artiq_reraise(void)
        __attribute__((noreturn));

#define artiq_raise_from_c(exnname, exnmsg, exnparam0, exnparam1, exnparam2) \
        do { \
          struct artiq_exception exn = { \
            .name = "0:artiq.coredevice.exceptions." exnname, \
            .message = exnmsg, \
            .param = { exnparam0, exnparam1, exnparam2 }, \
            .file = __FILE__, \
            .line = __LINE__, \
            .column = -1, \
            .function = __func__, \
          }; \
          __artiq_raise(&exn); \
        } while(0)

/* Called by the runtime */
void __artiq_terminate(struct artiq_exception *artiq_exn,
                       struct artiq_backtrace_item *backtrace,
                       size_t backtrace_size)
        __attribute__((noreturn));

#ifdef __cplusplus
}
#endif

#endif /* __ARTIQ_PERSONALITY_H */
