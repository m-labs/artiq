#ifndef __CORECOM_H
#define __CORECOM_H

typedef int (*object_loader)(void *, int);
typedef int (*kernel_runner)(const char *);

void corecom_serve(object_loader load_object, kernel_runner run_kernel);
int corecom_rpc(int rpc_num, int n_args, ...);
void corecom_log(const char *fmt, ...);

#endif /* __CORECOM_H */
