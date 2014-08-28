#ifndef __CORECOM_H
#define __CORECOM_H

int ident_and_download_kernel(void *buffer, int maxlength);
int rpc(int rpc_num, int n_args, ...);
void kernel_finished(void);

#endif /* __CORECOM_H */
