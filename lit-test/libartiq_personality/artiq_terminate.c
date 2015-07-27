#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>
#include <unwind.h>
#include <artiq_personality.h>

#define __USE_GNU
#include <dlfcn.h>

void __artiq_terminate(struct artiq_exception *exn,
                       struct artiq_backtrace_item *backtrace,
                       size_t backtrace_size) {
  printf("Uncaught %s: %s (%"PRIi64", %"PRIi64", %"PRIi64")\n"
         "at %s:%"PRIi32":%"PRIi32"\n",
         exn->name, exn->message,
         exn->param[0], exn->param[1], exn->param[1],
         exn->file, exn->line, exn->column + 1);

  for(size_t i = 0; i < backtrace_size; i++) {
    Dl_info info;
    if(dladdr((void*) backtrace[i].function, &info) && info.dli_sname) {
      printf("at %s+%p\n", info.dli_sname, (void*)backtrace[i].offset);
    } else {
      printf("at %p+%p\n", (void*)backtrace[i].function, (void*)backtrace[i].offset);
    }
  }

  exit(1);
}
