/*
 * Yann Sionneau <ys@m-labs.hk>, 2015
 */

#ifndef __FLASH_STORAGE_H
#define __FLASH_STORAGE_H

void fs_erase(void);
void fs_write(char *key, void *buffer, unsigned int buflen);
unsigned int fs_read(char *key, void *buffer, unsigned int buflen, unsigned int *remain);

#endif /* __FLASH_STORAGE_H */
