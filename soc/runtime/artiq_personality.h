#ifndef __ARTIQ_PERSONALITY_H
#define __ARTIQ_PERSONALITY_H

#include <stdint.h>

struct artiq_exception {
  union {
    uintptr_t typeinfo;
    const char *name;
  };
  const char *file;
  int32_t line;
  int32_t column;
  const char *message;
  int64_t param[3];
};

#ifdef __cplusplus
extern "C" {
#endif

void __artiq_terminate(struct artiq_exception *artiq_exn)
        __attribute__((noreturn));

void __artiq_raise(struct artiq_exception *artiq_exn);

#ifdef __cplusplus
}
#endif

#endif /* __ARTIQ_PERSONALITY_H */
