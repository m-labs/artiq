#ifndef __EXCEPTIONS_H
#define __EXCEPTIONS_H

#include <setjmp.h>

struct exception_env {
	jmp_buf jb;
	struct exception_env *prev;
};

int exception_catch(struct exception_env *ee, int *id);
void exception_pop(void);
void exception_raise(int id) __attribute__((noreturn));

#endif /* __EXCEPTIONS_H */
