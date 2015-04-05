#ifndef __COMM_H
#define __COMM_H

enum {
    KERNEL_RUN_INVALID_STATUS,

    KERNEL_RUN_FINISHED,
    KERNEL_RUN_EXCEPTION,
    KERNEL_RUN_STARTUP_FAILED
};

typedef int (*object_loader)(void *, int);
typedef int (*kernel_runner)(const char *, int *, long long int *);

void comm_serve(object_loader load_object, kernel_runner run_kernel);
int comm_rpc(int rpc_num, ...);
void comm_log(const char *fmt, ...);

#endif /* __COMM_H */
