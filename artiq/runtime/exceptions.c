#include <generated/csr.h>

#include "log.h"
#include "exceptions.h"

#define MAX_EXCEPTION_CONTEXTS 64

struct exception_context {
    void *jb[13];
};

static struct exception_context exception_contexts[MAX_EXCEPTION_CONTEXTS];
static int ec_top;
static int stored_id;
static long long int stored_params[3];

void *exception_push(void)
{
    if(ec_top >= MAX_EXCEPTION_CONTEXTS)
        exception_raise(EID_INTERNAL_ERROR);
    return exception_contexts[ec_top++].jb;
}

void exception_pop(int levels)
{
    ec_top -= levels;
}

int exception_getid(long long int *eparams)
{
    int i;

    if(eparams)
        for(i=0;i<3;i++)
            eparams[i] = stored_params[i];
    return stored_id;
}

void exception_raise(int id)
{
    exception_raise_params(id, 0, 0, 0);
}

void exception_raise_params(int id,
    long long int p0, long long int p1,
    long long int p2)
{
    if(ec_top > 0) {
        stored_id = id;
        stored_params[0] = p0;
        stored_params[1] = p1;
        stored_params[2] = p2;
        exception_longjmp(exception_contexts[--ec_top].jb);
    } else {
        log("ERROR: uncaught exception, ID=%d\n", id);
        while(1);
    }
}
