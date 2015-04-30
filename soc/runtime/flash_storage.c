/*
 * Yann Sionneau <ys@m-labs.hk>, 2015
 */

#include <string.h>
#include <system.h>
#include <spiflash.h>
#include <generated/mem.h>
#include <generated/csr.h>

#include "flash_storage.h"

#if (defined CSR_SPIFLASH_BASE && defined SPIFLASH_PAGE_SIZE)

#define STORAGE_ADDRESS ((char *)(FLASH_BOOT_ADDRESS + 256*1024))
#define STORAGE_SIZE    SPIFLASH_SECTOR_SIZE
#define END_MARKER      (0xFFFFFFFF)

#define min(a, b) (a>b?b:a)
#define max(a, b) (a>b?a:b)

#define goto_next_record(buff, addr) do { \
        unsigned int key_size = strlen(&buff[addr])+1; \
        if(key_size % 4) \
            key_size += 4 - (key_size % 4); \
        unsigned int *buflen_p = (unsigned int *)&buff[addr + key_size]; \
        unsigned int buflen = *buflen_p; \
        if(buflen % 4) \
            buflen += 4 - (buflen % 4); \
        addr += key_size + sizeof(int) + buflen; \
    } while (0)

union seek {
    unsigned int integer;
    char bytes[4];
};

static void write_at_offset(char *key, void *buffer, int buflen, unsigned int sector_offset);
static char key_exists(char *buff, char *key, char *end);
static char check_for_duplicates(char *buff);
static unsigned int try_to_flush_duplicates(void);

static char key_exists(char *buff, char *key, char *end)
{
    unsigned int addr;

    addr = 0;
    while(&buff[addr] < end && *(unsigned int*)&buff[addr] != END_MARKER) {
        if(strcmp(&buff[addr], key) == 0)
            return 1;
        goto_next_record(buff, addr);
    }
    return 0;
}

static char check_for_duplicates(char *buff)
{
    unsigned int addr;
    char *key_name;

    addr = 0;
    while(addr < STORAGE_SIZE && *(unsigned int *)&buff[addr] != END_MARKER) {
        key_name = &buff[addr];
        goto_next_record(buff, addr);
        if(key_exists(&buff[addr], key_name, &buff[STORAGE_SIZE]))
            return 1;
    }

    return 0;
}

static unsigned int try_to_flush_duplicates(void)
{
    unsigned int addr, i, key_size, buflen;
    char *key_name, *last_duplicate;
    char sector_buff[STORAGE_SIZE];
    union seek *seeker = (union seek *)sector_buff;

    memcpy(sector_buff, STORAGE_ADDRESS, STORAGE_SIZE);
    if(check_for_duplicates(sector_buff)) {
        fs_erase();
        for(addr = 0; addr < STORAGE_SIZE && seeker[addr >> 2].integer != END_MARKER;) {
            key_name = &sector_buff[addr];
            key_size = strlen(key_name)+1;
            if(key_size % 4)
                key_size += 4 - (key_size % 4);
            if(!key_exists((char *)STORAGE_ADDRESS, key_name, STORAGE_ADDRESS+STORAGE_SIZE)) {
                last_duplicate = key_name;
                for(i = addr; i < STORAGE_SIZE;) {
                    goto_next_record(sector_buff, i);
                    if(strcmp(&sector_buff[i], key_name) == 0)
                        last_duplicate = &sector_buff[i];
                }
                buflen = *(unsigned int *)&last_duplicate[key_size];
                fs_write(key_name, &last_duplicate[key_size+sizeof(int)], buflen);
            }
            goto_next_record(sector_buff, addr);
        }
        return 0;
    } else
        return 1;
}

static void write_at_offset(char *key, void *buffer, int buflen, unsigned int sector_offset)
{
    int key_len = strlen(key) + 1;
    int key_len_alignment = 0, buflen_alignment = 0;
    unsigned char padding[3] = {0, 0, 0};

    if(key_len % 4)
        key_len_alignment = 4 - (key_len % 4);

    if(buflen % 4)
        buflen_alignment = 4 - (buflen % 4);

    write_to_flash(sector_offset, (unsigned char *)key, key_len);
    write_to_flash(sector_offset+key_len, padding, key_len_alignment);
    write_to_flash(sector_offset+key_len+key_len_alignment, (unsigned char *)&buflen, sizeof(buflen));
    write_to_flash(sector_offset+key_len+key_len_alignment+sizeof(buflen), buffer, buflen);
    write_to_flash(sector_offset+key_len+key_len_alignment+sizeof(buflen)+buflen, padding, buflen_alignment);
    flush_cpu_dcache();
}


void fs_write(char *key, void *buffer, unsigned int buflen)
{
    char *addr;
    unsigned int key_size = strlen(key)+1;
    unsigned int record_size = key_size + sizeof(int) + buflen;

    for(addr = STORAGE_ADDRESS; addr < STORAGE_ADDRESS + STORAGE_SIZE - record_size; addr += 4) {
        if(*(unsigned int *)addr == END_MARKER) {
            write_at_offset(key, buffer, buflen, (unsigned int)addr);
            break;
        }
    }
    if(addr >= STORAGE_ADDRESS + STORAGE_SIZE - record_size) { // Flash is full? Try to flush duplicates.
        if(try_to_flush_duplicates())
            return; // No duplicates found, cannot write the new key-value record: sector is full.

        // Now retrying to write, hoping enough flash was freed.
        for(addr = STORAGE_ADDRESS; addr < STORAGE_ADDRESS + STORAGE_SIZE - record_size; addr += 4) {
            if(*(unsigned int *)addr == END_MARKER) {
                write_at_offset(key, buffer, buflen, (unsigned int)addr);
                break;
            }
        }
    }
}

void fs_erase(void)
{
    erase_flash_sector((unsigned int)STORAGE_ADDRESS);
    flush_cpu_dcache();
}

unsigned int fs_read(char *key, void *buffer, unsigned int buflen, unsigned int *remain)
{
    unsigned int read_length = 0;
    char *addr;

    addr = STORAGE_ADDRESS;
    while(addr < (STORAGE_ADDRESS + STORAGE_SIZE) && (*addr != END_MARKER)) {
        unsigned int key_len, value_len;
        char *key_addr = addr;

        key_len = strlen(addr) + 1;
        if(key_len % 4)
            key_len += 4 - (key_len % 4);
        addr += key_len;
        value_len = *(unsigned int *)addr;
        addr += sizeof(value_len);
        if(strcmp(key_addr, key) == 0) {
            memcpy(buffer, addr, min(value_len, buflen));
            read_length = min(value_len, buflen);
            if(remain)
                *remain = max(0, (int)value_len - (int)buflen);
        }
        addr += value_len;
        if((int)addr % 4)
            addr += 4 - ((int)addr % 4);
    }
    return read_length;
}

#endif /* CSR_SPIFLASH_BASE && SPIFLASH_PAGE_SIZE */
