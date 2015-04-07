/*
 * Yann Sionneau <ys@m-labs.hk>, 2015
 */

#ifndef __FLASH_STORAGE_H
#define __FLASH_STORAGE_H

void write(char *key, void *buffer, unsigned int buflen);
unsigned int read(char *key, void *buffer, unsigned int buflen, unsigned int *remain);

#endif /* __FLASH_STORAGE_H */
