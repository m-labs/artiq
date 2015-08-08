/*
 * Yann Sionneau <ys@m-labs.hk>, 2015
 */

#ifndef __FLASH_STORAGE_H
#define __FLASH_STORAGE_H

void fs_remove(const char *key);
void fs_erase(void);
int fs_write(const char *key, const void *buffer, unsigned int buflen);
unsigned int fs_read(const char *key, void *buffer, unsigned int buflen, unsigned int *remain);

#endif /* __FLASH_STORAGE_H */
