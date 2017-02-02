#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>
#include <unwind.h>
#include <artiq_personality.h>

#define __USE_GNU
#include <dlfcn.h>

void __artiq_terminate(struct artiq_exception *exn,
                       struct slice backtrace) {
  printf("Uncaught %s: %s (%"PRIi64", %"PRIi64", %"PRIi64")\n"
         "at %s:%"PRIi32":%"PRIi32"\n",
         exn->name, exn->message,
         exn->param[0], exn->param[1], exn->param[1],
         exn->file, exn->line, exn->column + 1);

  for(size_t i = 0; i < backtrace.len; i++) {
    printf("at %"PRIxPTR"\n", ((uintptr_t*)backtrace.ptr)[i]);
  }

  exit(1);
}
