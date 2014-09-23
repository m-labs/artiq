#include "exceptions.h"
#include "corecom.h"

#define MAX_EXCEPTION_CONTEXTS 64

struct exception_context {
    void *jb[13];
};

static struct exception_context exception_contexts[MAX_EXCEPTION_CONTEXTS];
static int ec_top;
static int stored_id;

void *exception_push(void)
{
    if(ec_top >= MAX_EXCEPTION_CONTEXTS)
        exception_raise(EID_NOMEM);
    return exception_contexts[ec_top++].jb;
}

void exception_pop(int levels)
{
    ec_top -= levels;
}

int exception_getid(void)
{
    return stored_id;
}

void exception_raise(int id)
{
    exception_longjmp(exception_contexts[--ec_top].jb);
}
