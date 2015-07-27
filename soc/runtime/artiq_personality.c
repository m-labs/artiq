#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <unwind.h>
#include "artiq_personality.h"

#define ARTIQ_EXCEPTION_CLASS 0x4152545141525451LL // 'ARTQARTQ'

struct artiq_raised_exception {
  struct _Unwind_Exception unwind;
  struct artiq_exception artiq;
};

static void __artiq_cleanup(_Unwind_Reason_Code reason, struct _Unwind_Exception *exc) {
  struct artiq_raised_exception *inflight = (struct artiq_raised_exception*) exc;
  // The in-flight exception is statically allocated, so we don't need to free it.
  // But, we clear it to mark it as processed.
  memset(&inflight->artiq, 0, sizeof(struct artiq_exception));
}

void __artiq_raise(struct artiq_exception *artiq_exn) {
  static struct artiq_raised_exception inflight;
  memcpy(&inflight.artiq, artiq_exn, sizeof(struct artiq_exception));
  inflight.unwind.exception_class = ARTIQ_EXCEPTION_CLASS;
  inflight.unwind.exception_cleanup = &__artiq_cleanup;

  _Unwind_Reason_Code result = _Unwind_RaiseException(&inflight.unwind);
  if(result == _URC_END_OF_STACK) {
    __artiq_terminate(&inflight.artiq);
  } else {
    fprintf(stderr, "__artiq_raise: unexpected error (%d)\n", result);
    abort();
  }
}

_Unwind_Reason_Code __artiq_personality(
        int version, _Unwind_Action actions, uint64_t exceptionClass,
        struct _Unwind_Exception *exceptionObject, struct _Unwind_Context *context) {
  abort();
}
