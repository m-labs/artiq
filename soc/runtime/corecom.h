#ifndef __CORECOM_H
#define __CORECOM_H

enum {
	KERNEL_RUN_FINISHED,
	KERNEL_RUN_EXCEPTION,
	KERNEL_RUN_STARTUP_FAILED
};

typedef int (*object_loader)(void *, int);
typedef int (*kernel_runner)(const char *, int *);

void corecom_serve(object_loader load_object, kernel_runner run_kernel);
int corecom_rpc(int rpc_num, int n_args, ...);
void corecom_log(const char *fmt, ...);

#endif /* __CORECOM_H */
