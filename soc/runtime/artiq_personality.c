#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <unwind.h>

struct artiq_exception {
  const char *name;
  const char *file;
  int32_t line;
  int32_t column;
  const char *message;
  int64_t param[3];
};

void __artiq_raise(struct artiq_exception *artiq_exn) {
  printf("raised %s\n", artiq_exn->name);
  abort();
}

_Unwind_Reason_Code __artiq_personality(int version,
    _Unwind_Action actions, uint64_t exceptionClass,
    struct _Unwind_Exception *exceptionObject,
    struct _Unwind_Context *context) {
  abort();
}
