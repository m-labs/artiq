#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>
#include <unwind.h>
#include <artiq_personality.h>

void __artiq_terminate(struct artiq_exception *exn) {
  printf("Uncaught %s: %s (%"PRIi64", %"PRIi64", %"PRIi64")\n"
         "at %s:%"PRIi32":%"PRIi32"",
         exn->name, exn->message,
         exn->param[0], exn->param[1], exn->param[1],
         exn->file, exn->line, exn->column + 1);
  exit(1);
}
