/*
 * Yann Sionneau <ys@m-labs.hk>, 2015
 */

#include <string.h>
#include <stdio.h>
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

struct record {
    char *key;
    unsigned int key_len;
    char *value;
    unsigned int value_len;
    char *raw_record;
    unsigned int size;
};

struct iter_state {
    char *buffer;
    unsigned int seek;
    unsigned int buf_len;
};

static unsigned int get_record_size(char *buff)
{
    unsigned int record_size;

    memcpy(&record_size, buff, 4);
    return record_size;
}

static void record_iter_init(struct iter_state *is, char *buffer, unsigned int buf_len)
{
    is->buffer = buffer;
    is->seek = 0;
    is->buf_len = buf_len;
}

static int record_iter_next(struct iter_state *is, struct record *record, int *fatal)
{
    if(is->seek >= is->buf_len)
        return 0;

    record->raw_record = &is->buffer[is->seek];
    record->size = get_record_size(record->raw_record);

    if(record->size == END_MARKER)
        return 0;

    if(is->seek > is->buf_len - sizeof(record->size) - 2) { /* 2 is the minimum key length */
        printf("flash_storage might be corrupted: END_MARKER missing at the end of the storage sector\n");
        if(fatal)
            *fatal = 1;
        return 0;
    }

    if(record->size > is->buf_len - is->seek) {
        printf("flash_storage might be corrupted: invalid record_size %d at address %08x\n", record->size, record->raw_record);
        if(fatal)
            *fatal = 1;
        return 0;
    }

    record->key = record->raw_record + sizeof(record->size);
    record->key_len = strnlen(record->key, record->size - sizeof(record->size)) + 1;

    if(record->key_len == record->size - sizeof(record->size) + 1) {
        printf("flash_storage might be corrupted: invalid key length at address %08x\n", record->raw_record);
        if(fatal)
            *fatal = 1;
        return 0;
    }

    record->value = record->key + record->key_len;
    record->value_len = record->size - record->key_len - sizeof(record->size);

    is->seek += record->size;
    return 1;
}

static unsigned int get_free_space(void)
{
    struct iter_state is;
    struct record record;

    record_iter_init(&is, STORAGE_ADDRESS, STORAGE_SIZE);
    while(record_iter_next(&is, &record, NULL));
    return STORAGE_SIZE - is.seek;
}

static int is_empty(struct record *record)
{
    return record->value_len == 0;
}

static int key_exists(char *buff, char *key, char *end, char accept_empty, struct record *found_record)
{
    struct iter_state is;
    struct record iter_record;
    int found = 0;

    record_iter_init(&is, buff, end - buff);
    while(record_iter_next(&is, &iter_record, NULL)) {
        if(strcmp(iter_record.key, key) == 0) {
            found = 1;
            if(found_record)
                *found_record = iter_record;
        }
    }

    if(found && is_empty(found_record) && !accept_empty)
        return 0;

    if(found)
        return 1;

    return 0;
}

static char check_for_duplicates(char *buff)
{
    struct record record, following_record;
    struct iter_state is;
    int no_error;

    record_iter_init(&is, buff, STORAGE_SIZE);
    no_error = record_iter_next(&is, &record, NULL);
    while(no_error) {
        no_error = record_iter_next(&is, &following_record, NULL);
        if(no_error && key_exists(following_record.raw_record, record.key, &buff[STORAGE_SIZE], 1, NULL))
            return 1;
        record = following_record;
    }

    return 0;
}

static char check_for_empty_records(char *buff)
{
    struct iter_state is;
    struct record record;

    record_iter_init(&is, buff, STORAGE_SIZE);
    while(record_iter_next(&is, &record, NULL))
        if(is_empty(&record))
            return 1;

    return 0;
}

static unsigned int try_to_flush_duplicates(char *new_key, unsigned int buf_len)
{
    unsigned int key_size, new_record_size, ret = 0, can_rollback = 0;
    struct record record, previous_record;
    char sector_buff[STORAGE_SIZE];
    struct iter_state is;

    memcpy(sector_buff, STORAGE_ADDRESS, STORAGE_SIZE);
    if(check_for_duplicates(sector_buff)
       || key_exists(sector_buff, new_key, &sector_buff[STORAGE_SIZE], 0, NULL)
       || check_for_empty_records(sector_buff)) {
        fs_erase();
        record_iter_init(&is, sector_buff, STORAGE_SIZE);
        while(record_iter_next(&is, &record, NULL)) {
            if(is_empty(&record))
                continue;
            if(!key_exists((char *)STORAGE_ADDRESS, record.key, STORAGE_ADDRESS + STORAGE_SIZE, 1, NULL)) {
                struct record rec;

                if(!key_exists(sector_buff, record.key, &sector_buff[STORAGE_SIZE], 0, &rec))
                    continue;
                if(strcmp(new_key, record.key) == 0) { // If we are about to write this key we don't keep the old value.
                    previous_record = rec; // This holds the old record in case we need it back (for instance if new record is too long)
                    can_rollback = 1;
                } else
                    fs_write(record.key, rec.value, rec.value_len);
            }
        }
        ret = 1;
    }

    key_size = strlen(new_key) + 1;
    new_record_size = key_size + buf_len + sizeof(new_record_size);
    if(can_rollback && new_record_size > get_free_space()) {
        fs_write(new_key, previous_record.value, previous_record.value_len);
    }

    return ret;
}

static void write_at_offset(char *key, void *buffer, int buf_len, unsigned int sector_offset)
{
    int key_len = strlen(key) + 1;
    unsigned int record_size = key_len + buf_len + sizeof(record_size);
    unsigned int flash_addr = (unsigned int)STORAGE_ADDRESS + sector_offset;

    write_to_flash(flash_addr, (unsigned char *)&record_size, sizeof(record_size));
    write_to_flash(flash_addr+sizeof(record_size), (unsigned char *)key, key_len);
    write_to_flash(flash_addr+sizeof(record_size)+key_len, buffer, buf_len);
    flush_cpu_dcache();
}


int fs_write(char *key, void *buffer, unsigned int buf_len)
{
    struct record record;
    unsigned int key_size = strlen(key) + 1;
    unsigned int new_record_size = key_size + sizeof(int) + buf_len;
    int no_error, fatal = 0;
    struct iter_state is;

    record_iter_init(&is, STORAGE_ADDRESS, STORAGE_SIZE);
    while((no_error = record_iter_next(&is, &record, &fatal)));

    if(fatal)
        goto fatal_error;

    if(STORAGE_SIZE - is.seek >= new_record_size) {
        write_at_offset(key, buffer, buf_len, is.seek);
        return 1;
    }

    if(!try_to_flush_duplicates(key, buf_len)) // storage is full, let's try to free some space up.
        return 0; // No duplicates found, cannot write the new key-value record: sector is full.
    // Now retrying to write, hoping enough flash was freed.

    record_iter_init(&is, STORAGE_ADDRESS, STORAGE_SIZE);
    while((no_error = record_iter_next(&is, &record, &fatal)));

    if(fatal)
        goto fatal_error;

    if(STORAGE_SIZE - is.seek >= new_record_size) {
        write_at_offset(key, buffer, buf_len, is.seek);
        return 1; // We eventually succeeded in writing the record
    } else
        return 0; // Storage is definitely full.

fatal_error:
    printf("fatal error: flash storage might be corrupted\n");
    return 0;
}

void fs_erase(void)
{
    erase_flash_sector((unsigned int)STORAGE_ADDRESS);
    flush_cpu_dcache();
}

unsigned int fs_read(char *key, void *buffer, unsigned int buf_len, unsigned int *remain)
{
    unsigned int read_length = 0;
    struct iter_state is;
    struct record record;
    int fatal = 0;

    if(remain)
        *remain = 0;

    record_iter_init(&is, STORAGE_ADDRESS, STORAGE_SIZE);
    while(record_iter_next(&is, &record, &fatal)) {
        if(strcmp(record.key, key) == 0) {
            memcpy(buffer, record.value, min(record.value_len, buf_len));
            read_length = min(record.value_len, buf_len);
            if(remain)
                *remain = max(0, (int)(record.value_len) - (int)buf_len);
        }
    }

    if(fatal)
        printf("fatal error: flash storage might be corrupted\n");

    return read_length;
}

void fs_remove(char *key)
{
    fs_write(key, NULL, 0);
}

#endif /* CSR_SPIFLASH_BASE && SPIFLASH_PAGE_SIZE */
