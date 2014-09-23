#ifndef __EXCEPTIONS_H
#define __EXCEPTIONS_H

enum {
	EID_NOMEM = 0
};

void *exception_push(void);
void exception_pop(int levels);
int exception_getid(void);
void exception_raise(int id) __attribute__((noreturn));

#endif /* __EXCEPTIONS_H */
