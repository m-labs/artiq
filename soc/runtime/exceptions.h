#ifndef __EXCEPTIONS_H
#define __EXCEPTIONS_H

enum {
    EID_NONE = 0,
    EID_INTERNAL_ERROR = 1,
    EID_RPC_EXCEPTION = 2,
    EID_RTIO_UNDERFLOW = 3,
    EID_RTIO_SEQUENCE_ERROR = 4,
    EID_RTIO_COLLISION_ERROR = 5,
    EID_RTIO_OVERFLOW = 6,
    EID_DDS_BATCH_ERROR = 7
};

int exception_setjmp(void *jb) __attribute__((returns_twice));
void exception_longjmp(void *jb) __attribute__((noreturn));

void *exception_push(void);
void exception_pop(int levels);
int exception_getid(long long int *eparams);
void exception_raise(int id) __attribute__((noreturn));
void exception_raise_params(int id,
    long long int p0, long long int p1,
    long long int p2) __attribute__((noreturn));

#endif /* __EXCEPTIONS_H */
