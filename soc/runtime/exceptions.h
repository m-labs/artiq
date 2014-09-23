#ifndef __EXCEPTIONS_H
#define __EXCEPTIONS_H

enum {
	EID_NOMEM = 0
};

int exception_setjmp(void *jb) __attribute__((returns_twice));
void exception_longjmp(void *jb, int val) __attribute__((noreturn));

void *exception_push(void);
void exception_pop(int levels);
int exception_getid(void);
void exception_raise(int id) __attribute__((noreturn));

#endif /* __EXCEPTIONS_H */
