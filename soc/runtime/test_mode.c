#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <irq.h>
#include <uart.h>
#include <generated/csr.h>
#include <console.h>

#include "dds.h"
#include "flash_storage.h"
#include "bridge_ctl.h"
#include "clock.h"
#include "test_mode.h"

static void leds(char *value)
{
    char *c;
    unsigned int value2;

    if(*value == 0) {
        printf("leds <value>\n");
        return;
    }

    value2 = strtoul(value, &c, 0);
    if(*c != 0) {
        printf("incorrect value\n");
        return;
    }

    leds_out_write(value2);
}

static void clksrc(char *value)
{
    char *c;
    unsigned int value2;

    if(*value == 0) {
        printf("clksrc <value>\n");
        return;
    }

    value2 = strtoul(value, &c, 0);
    if(*c != 0) {
        printf("incorrect value\n");
        return;
    }

    rtio_crg_clock_sel_write(value2);
}

static void ttloe(char *n, char *value)
{
    char *c;
    unsigned int n2, value2;

    if((*n == 0)||(*value == 0)) {
        printf("ttloe <n> <value>\n");
        return;
    }

    n2 = strtoul(n, &c, 0);
    if(*c != 0) {
        printf("incorrect channel\n");
        return;
    }
    value2 = strtoul(value, &c, 0);
    if(*c != 0) {
        printf("incorrect value\n");
        return;
    }

    brg_ttloe(n2, value2);
}

static void ttlo(char *n, char *value)
{
    char *c;
    unsigned int n2, value2;

    if((*n == 0)||(*value == 0)) {
        printf("ttlo <n> <value>\n");
        return;
    }

    n2 = strtoul(n, &c, 0);
    if(*c != 0) {
        printf("incorrect channel\n");
        return;
    }
    value2 = strtoul(value, &c, 0);
    if(*c != 0) {
        printf("incorrect value\n");
        return;
    }

    brg_ttlo(n2, value2);
}

static void ddssel(char *n)
{
    char *c;
    unsigned int n2;

    if(*n == 0) {
        printf("ddssel <n>\n");
        return;
    }

    n2 = strtoul(n, &c, 0);
    if(*c != 0) {
        printf("incorrect channel\n");
        return;
    }

#ifdef DDS_ONEHOT_SEL
    n2 = 1 << n2;
#endif
    brg_ddssel(n2);
}

static void ddsw(char *addr, char *value)
{
    char *c;
    unsigned int addr2, value2;

    if((*addr == 0) || (*value == 0)) {
        printf("ddsr <addr> <value>\n");
        return;
    }

    addr2 = strtoul(addr, &c, 0);
    if(*c != 0) {
        printf("incorrect address\n");
        return;
    }
    value2 = strtoul(value, &c, 0);
    if(*c != 0) {
        printf("incorrect value\n");
        return;
    }

    brg_ddswrite(addr2, value2);
}

static void ddsr(char *addr)
{
    char *c;
    unsigned int addr2;

    if(*addr == 0) {
        printf("ddsr <addr>\n");
        return;
    }

    addr2 = strtoul(addr, &c, 0);
    if(*c != 0) {
        printf("incorrect address\n");
        return;
    }

#ifdef DDS_AD9858
    printf("0x%02x\n", brg_ddsread(addr2));
#endif
#ifdef DDS_AD9914
    printf("0x%04x\n", brg_ddsread(addr2));
#endif
}

static void ddsfud(void)
{
    brg_ddsfud();
}

static void ddsftw(char *n, char *ftw)
{
    char *c;
    unsigned int n2, ftw2;

    if((*n == 0) || (*ftw == 0)) {
        printf("ddsftw <n> <ftw>\n");
        return;
    }

    n2 = strtoul(n, &c, 0);
    if(*c != 0) {
        printf("incorrect channel\n");
        return;
    }
    ftw2 = strtoul(ftw, &c, 0);
    if(*c != 0) {
        printf("incorrect value\n");
        return;
    }

#ifdef DDS_ONEHOT_SEL
    n2 = 1 << n2;
#endif
    brg_ddssel(n2);

#ifdef DDS_AD9858
    brg_ddswrite(DDS_FTW0, ftw2 & 0xff);
    brg_ddswrite(DDS_FTW1, (ftw2 >> 8) & 0xff);
    brg_ddswrite(DDS_FTW2, (ftw2 >> 16) & 0xff);
    brg_ddswrite(DDS_FTW3, (ftw2 >> 24) & 0xff);
#endif
#ifdef DDS_AD9914
    brg_ddswrite(DDS_FTWL, ftw2 & 0xffff);
    brg_ddswrite(DDS_FTWH, (ftw2 >> 16) & 0xffff);
#endif

    brg_ddsfud();
}

static void ddsreset(void)
{
    brg_ddsreset();
}

#ifdef DDS_AD9858
static void ddsinit(void)
{
    brg_ddsreset();
    brg_ddswrite(DDS_CFR0, 0x78);
    brg_ddswrite(DDS_CFR1, 0x00);
    brg_ddswrite(DDS_CFR2, 0x00);
    brg_ddswrite(DDS_CFR3, 0x00);
    brg_ddsfud();
}
#endif

#ifdef DDS_AD9914
static void ddsinit(void)
{
    long long int t;

    brg_ddsreset();
    brg_ddswrite(DDS_CFR1L, 0x0008);
    brg_ddswrite(DDS_CFR1H, 0x0000);
    brg_ddswrite(DDS_CFR4H, 0x0105);
    brg_ddswrite(DDS_FUD, 0);
    t = clock_get_ms();
    while(clock_get_ms() < t + 2);
    brg_ddswrite(DDS_CFR4H, 0x0005);
    brg_ddsfud();
}
#endif

static void ddstest_one(unsigned int i)
{
    unsigned int v[12] = {
        0xaaaaaaaa, 0x55555555, 0xa5a5a5a5, 0x5a5a5a5a,
        0x00000000, 0xffffffff, 0x12345678, 0x87654321,
        0x0000ffff, 0xffff0000, 0x00ff00ff, 0xff00ff00,
    };
    unsigned int f, g, j;

    brg_ddssel(i);
    ddsinit();

    for(j=0; j<12; j++) {
        f = v[j];
#ifdef DDS_AD9858
        brg_ddswrite(DDS_FTW0, f & 0xff);
        brg_ddswrite(DDS_FTW1, (f >> 8) & 0xff);
        brg_ddswrite(DDS_FTW2, (f >> 16) & 0xff);
        brg_ddswrite(DDS_FTW3, (f >> 24) & 0xff);
#endif
#ifdef DDS_AD9914
        brg_ddswrite(DDS_FTWL, f & 0xffff);
        brg_ddswrite(DDS_FTWH, (f >> 16) & 0xffff);
#endif
        brg_ddsfud();
#ifdef DDS_AD9858
        g = brg_ddsread(DDS_FTW0);
        g |= brg_ddsread(DDS_FTW1) << 8;
        g |= brg_ddsread(DDS_FTW2) << 16;
        g |= brg_ddsread(DDS_FTW3) << 24;
#endif
#ifdef DDS_AD9914
        g = brg_ddsread(DDS_FTWL);
        g |= brg_ddsread(DDS_FTWH) << 16;
#endif
        if(g != f)
            printf("readback fail on DDS %d, 0x%08x != 0x%08x\n", i, g, f);
    }
}

static void ddstest(char *n)
{
    int i, j;
    char *c;
    unsigned int n2;

    if (*n == 0) {
        printf("ddstest <cycles>\n");
        return;
    }
    n2 = strtoul(n, &c, 0);

    for(i=0; i<n2; i++) {
        for(j=0; j<8; j++) {
            ddstest_one(j);
        }
    }
}

#if (defined CSR_SPIFLASH_BASE && defined SPIFLASH_PAGE_SIZE)
static void fsread(char *key)
{
    char readbuf[SPIFLASH_SECTOR_SIZE];
    int r;

    r = fs_read(key, readbuf, sizeof(readbuf)-1, NULL);
    readbuf[r] = 0;
    if(r == 0)
        printf("key %s does not exist\n", key);
    else
        puts(readbuf);
}

static void fswrite(char *key, void *buffer, unsigned int length)
{
    if(!fs_write(key, buffer, length))
        printf("cannot write key %s because flash storage is full\n", key);
}

static void fsfull(void)
{
    int i;
    char value[4096];
    memset(value, '@', sizeof(value));

    for(i = 0; i < SPIFLASH_SECTOR_SIZE/sizeof(value); i++)
        fs_write("plip", value, sizeof(value));
}

static void check_read(char *key, char *expected, unsigned int length, unsigned int testnum)
{
    char readbuf[SPIFLASH_SECTOR_SIZE];
    unsigned int remain, readlength;

    memset(readbuf, '\0', sizeof(readbuf));

    readlength = fs_read(key, readbuf, sizeof(readbuf), &remain);
    if(remain > 0)
        printf("KO[%u] remain == %u, expected 0\n", testnum, remain);
    if(readlength != length)
        printf("KO[%u] read length == %u, expected %u\n", testnum, readlength, length);
    if(remain == 0 && readlength == length)
        printf(".");

    readbuf[readlength] = 0;
    if(memcmp(expected, readbuf, readlength) == 0)
        printf(".\n");
    else
        printf("KO[%u] read %s instead of %s\n", testnum, readbuf, expected);
}

static void check_doesnt_exist(char *key, unsigned int testnum)
{
    char readbuf;
    unsigned int remain, readlength;

    readlength = fs_read(key, &readbuf, sizeof(readbuf), &remain);
    if(remain > 0)
        printf("KO[%u] remain == %u, expected 0\n", testnum, remain);
    if(readlength > 0)
        printf("KO[%u] readlength == %d, expected 0\n", testnum, readlength);
    if(remain == 0 && readlength == 0)
        printf(".\n");
}

static void check_write(unsigned int ret)
{
    if(!ret)
        printf("KO");
    else
        printf(".");
}

static inline void test_sector_is_full(void)
{
    char c;
    char value[4096];
    char key[2] = {0, 0};

    fs_erase();
    memset(value, '@', sizeof(value));
    for(c = 1; c <= SPIFLASH_SECTOR_SIZE/sizeof(value); c++) {
        key[0] = c;
        check_write(fs_write(key, value, sizeof(value) - 6));
    }
    check_write(!fs_write("this_should_fail", "fail", 5));
    printf("\n");
}

static void test_one_big_record(int testnum)
{
    char value[SPIFLASH_SECTOR_SIZE];
    memset(value, '@', sizeof(value));

    fs_erase();
    check_write(fs_write("a", value, sizeof(value) - 6));
    check_read("a", value, sizeof(value) - 6, testnum);
    check_write(fs_write("a", value, sizeof(value) - 6));
    check_read("a", value, sizeof(value) - 6, testnum);
    check_write(!fs_write("b", value, sizeof(value) - 6));
    check_read("a", value, sizeof(value) - 6, testnum);
    fs_remove("a");
    check_doesnt_exist("a", testnum);
    check_write(fs_write("a", value, sizeof(value) - 6));
    check_read("a", value, sizeof(value) - 6, testnum);
    fs_remove("a");
    check_doesnt_exist("a", testnum);
    value[0] = '!';
    check_write(fs_write("b", value, sizeof(value) - 6));
    check_read("b", value, sizeof(value) - 6, testnum);
}

static void test_flush_duplicate_rollback(int testnum)
{
    char value[SPIFLASH_SECTOR_SIZE];
    memset(value, '@', sizeof(value));

    fs_erase();
    /* This makes the flash storage full with one big record */
    check_write(fs_write("a", value, SPIFLASH_SECTOR_SIZE - 6));
    /* This should trigger the try_to_flush_duplicate code which
     * at first will not keep the old "a" record value because we are
     * overwriting it. But then it should roll back to the old value
     * because the new record is too large.
     */
    value[0] = '!';
    check_write(!fs_write("a", value, sizeof(value)));
    /* check we still have the old record value */
    value[0] = '@';
    check_read("a", value, SPIFLASH_SECTOR_SIZE - 6, testnum);
}

static void test_too_big_fails(int testnum)
{
    char value[SPIFLASH_SECTOR_SIZE];
    memset(value, '@', sizeof(value));

    fs_erase();
    check_write(!fs_write("a", value, sizeof(value) - 6 + /* TOO BIG */ 1));
    check_doesnt_exist("a", testnum);
}

static void fs_test(void)
{
    int i;
    char writebuf[] = "abcdefghijklmnopqrst";
    char read_check[4096];
    int vect_length = sizeof(writebuf);

    memset(read_check, '@', sizeof(read_check));
    printf("testing...\n");
    for(i = 0; i < vect_length; i++) {
        printf("%u.0:", i);
        fs_erase();
        check_write(fs_write("a", writebuf, i));
        check_read("a", writebuf, i, i);

        printf("%u.1:", i);
        fsfull();
        check_read("a", writebuf, i, i);

        printf("%u.2:", i);
        check_read("plip", read_check, sizeof(read_check), i);

        printf("%u.3:", i);
        check_write(fs_write("a", "b", 2));
        check_read("a", "b", 2, i);

        printf("%u.4:", i);
        fsfull();
        check_read("a", "b", 2, i);

        printf("%u.5:", i);
        check_doesnt_exist("notfound", i);

        printf("%u.6:", i);
        fs_remove("a");
        check_doesnt_exist("a", i);

        printf("%u.7:", i);
        fsfull();
        check_doesnt_exist("a", i);
    }

    printf("%u:", vect_length);
    test_sector_is_full();

    printf("%u:", vect_length+1);
    test_one_big_record(vect_length+1);

    printf("%u:", vect_length+2);
    test_flush_duplicate_rollback(vect_length+2);

    printf("%u:", vect_length+3);
    test_too_big_fails(vect_length+3);
}

#endif

static void help(void)
{
    puts("Available commands:");
    puts("help            - this message");
    puts("clksrc <n>      - select RTIO clock source");
    puts("ttloe <n> <v>   - set TTL output enable");
    puts("ttlo <n> <v>    - set TTL output value");
    puts("ddssel <n>      - select a DDS");
    puts("ddsinit         - reset, config, FUD DDS");
    puts("ddsreset        - reset DDS");
    puts("ddsw <a> <d>    - write to DDS register");
    puts("ddsr <a>        - read DDS register");
    puts("ddsfud          - pulse FUD");
    puts("ddsftw <n> <d>  - write FTW");
    puts("ddstest <n>     - perform test sequence on DDS");
    puts("leds <n>        - set LEDs");
#if (defined CSR_SPIFLASH_BASE && defined SPIFLASH_PAGE_SIZE)
    puts("fserase         - erase flash storage");
    puts("fswrite <k> <v> - write to flash storage");
    puts("fsread <k>      - read flash storage");
    puts("fsremove <k>    - remove a key-value record from flash storage");
    puts("fstest          - run flash storage tests. WARNING: erases the storage area");
#endif
}

static void readstr(char *s, int size)
{
    char c[2];
    int ptr;

    c[1] = 0;
    ptr = 0;
    while(1) {
        c[0] = readchar();
        switch(c[0]) {
            case 0x7f:
            case 0x08:
                if(ptr > 0) {
                    ptr--;
                    putsnonl("\x08 \x08");
                }
                break;
            case 0x07:
                break;
            case '\r':
            case '\n':
                s[ptr] = 0x00;
                putsnonl("\n");
                return;
            default:
                putsnonl(c);
                s[ptr] = c[0];
                ptr++;
                break;
        }
    }
}

static char *get_token(char **str)
{
    char *c, *d;

    c = (char *)strchr(*str, ' ');
    if(c == NULL) {
        d = *str;
        *str = *str+strlen(*str);
        return d;
    }
    *c = 0;
    d = *str;
    *str = c+1;
    return d;
}


static void do_command(char *c)
{
    char *token;

    token = get_token(&c);

    if(strcmp(token, "help") == 0) help();
    else if(strcmp(token, "leds") == 0) leds(get_token(&c));

    else if(strcmp(token, "clksrc") == 0) clksrc(get_token(&c));

    else if(strcmp(token, "ttloe") == 0) ttloe(get_token(&c), get_token(&c));
    else if(strcmp(token, "ttlo") == 0) ttlo(get_token(&c), get_token(&c));

    else if(strcmp(token, "ddssel") == 0) ddssel(get_token(&c));
    else if(strcmp(token, "ddsw") == 0) ddsw(get_token(&c), get_token(&c));
    else if(strcmp(token, "ddsr") == 0) ddsr(get_token(&c));
    else if(strcmp(token, "ddsreset") == 0) ddsreset();
    else if(strcmp(token, "ddsinit") == 0) ddsinit();
    else if(strcmp(token, "ddsfud") == 0) ddsfud();
    else if(strcmp(token, "ddsftw") == 0) ddsftw(get_token(&c), get_token(&c));
    else if(strcmp(token, "ddstest") == 0) ddstest(get_token(&c));

#if (defined CSR_SPIFLASH_BASE && defined SPIFLASH_PAGE_SIZE)
    else if(strcmp(token, "fserase") == 0) fs_erase();
    else if(strcmp(token, "fswrite") == 0) fswrite(get_token(&c), c, strlen(c));
    else if(strcmp(token, "fsread") == 0) fsread(get_token(&c));
    else if(strcmp(token, "fsremove") == 0) fs_remove(get_token(&c));
    else if(strcmp(token, "fstest") == 0) fs_test();
#endif

    else if(strcmp(token, "") != 0)
        printf("Command not found\n");
}

void test_main(void)
{
    char buffer[64];

    brg_start();

    while(1) {
        putsnonl("\e[1mtest>\e[0m ");
        readstr(buffer, 64);
        do_command(buffer);
    }
}
