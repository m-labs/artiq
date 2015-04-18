#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <irq.h>
#include <uart.h>
#include <generated/csr.h>
#include <console.h>

#include "dds.h"
#include "test_mode.h"

#ifdef ARTIQ_AMP

#include "kernelcpu.h"
#include "mailbox.h"
#include "messages.h"

static void amp_bridge_init(void)
{
    struct msg_base *umsg;

    kernelcpu_start(NULL);

    while(1) {
        umsg = mailbox_wait_and_receive();
        if(umsg->type == MESSAGE_TYPE_BRG_READY) {
            printf("AMP bridge ready\n");
            mailbox_acknowledge();
            break;
        } else {
            printf("Warning: unexpected message %d from AMP bridge\n", umsg->type);
            mailbox_acknowledge();
        }
    }
}

static void p_ttlout(int n, int value)
{
    struct msg_brg_ttl_out msg;

    msg.type = MESSAGE_TYPE_BRG_TTL_OUT;
    msg.channel = n;
    msg.value = value;
    mailbox_send_and_wait(&msg);
}

static void p_ddssel(int channel)
{
    struct msg_brg_dds_sel msg;

    msg.type = MESSAGE_TYPE_BRG_DDS_SEL;
    msg.channel = channel;
    mailbox_send_and_wait(&msg);
}

static void p_ddsreset(void)
{
    struct msg_base msg;

    msg.type = MESSAGE_TYPE_BRG_DDS_RESET;
    mailbox_send_and_wait(&msg);
}

static unsigned int p_ddsread(unsigned int address)
{
    struct msg_brg_dds_read_request msg;
    struct msg_brg_dds_read_reply *rmsg;
    unsigned int r;

    msg.type = MESSAGE_TYPE_BRG_DDS_READ_REQUEST;
    msg.address = address;
    mailbox_send(&msg);
    while(1) {
        rmsg = mailbox_wait_and_receive();
        if(rmsg->type == MESSAGE_TYPE_BRG_DDS_READ_REPLY) {
            r = rmsg->data;
            mailbox_acknowledge();
            return r;
        } else {
            printf("Warning: unexpected message %d from AMP bridge\n", rmsg->type);
            mailbox_acknowledge();
        }
    }
}

static void p_ddswrite(unsigned int address, unsigned int data)
{
    struct msg_brg_dds_write msg;

    msg.type = MESSAGE_TYPE_BRG_DDS_WRITE;
    msg.address = address;
    msg.data = data;
    mailbox_send_and_wait(&msg);
}

static void p_ddsfud(void)
{
    struct msg_base msg;

    msg.type = MESSAGE_TYPE_BRG_DDS_FUD;
    mailbox_send_and_wait(&msg);
}

#else /* ARTIQ_AMP */

#include "rtio.h"

static void p_ttlout(int n, int value)
{
    rtio_init();
    rtio_set_oe(rtio_get_counter() + 8000, n, 1);
    rtio_set_o(rtio_get_counter() + 8000, n, value);
}

static void p_ddssel(int channel)
{
    DDS_WRITE(DDS_GPIO, channel);
}

static void p_ddsreset(void)
{
    unsigned int g;

    g = DDS_READ(DDS_GPIO);
    DDS_WRITE(DDS_GPIO, g | (1 << 7));
    DDS_WRITE(DDS_GPIO, g);
}

static unsigned int p_ddsread(unsigned int address)
{
    return DDS_READ(address);
}

static void p_ddswrite(unsigned int address, unsigned int data)
{
    DDS_WRITE(address, data);
}

static void p_ddsfud(void)
{
    rtio_init();
    rtio_fud(rtio_get_counter() + 8000);
}

#endif /* ARTIQ_AMP */

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

    rtiocrg_clock_sel_write(value2);
}

static void ttlout(char *n, char *value)
{
    char *c;
    unsigned int n2, value2;

    if((*n == 0)||(*value == 0)) {
        printf("ttlout <n> <value>\n");
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

    p_ttlout(n2, value2);
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

    p_ddssel(n2);
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

    p_ddswrite(addr2, value2);
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

    printf("0x%02x\n", p_ddsread(addr2));
}

static void ddsfud(void)
{
    p_ddsfud();
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

    p_ddssel(n2);
    p_ddswrite(DDS_FTW0, ftw2 & 0xff);
    p_ddswrite(DDS_FTW1, (ftw2 >> 8) & 0xff);
    p_ddswrite(DDS_FTW2, (ftw2 >> 16) & 0xff);
    p_ddswrite(DDS_FTW3, (ftw2 >> 24) & 0xff);
    p_ddsfud();
}

static void ddsreset(void)
{
    p_ddsreset();
}

static void ddsinit(void)
{
    p_ddsreset();
    p_ddswrite(0x00, 0x78);
    p_ddswrite(0x01, 0x00);
    p_ddswrite(0x02, 0x00);
    p_ddswrite(0x03, 0x00);
    p_ddsfud();
}

static void ddstest_one(unsigned int i)
{
    unsigned int v[12] = {
        0xaaaaaaaa, 0x55555555, 0xa5a5a5a5, 0x5a5a5a5a,
        0x00000000, 0xffffffff, 0x12345678, 0x87654321,
        0x0000ffff, 0xffff0000, 0x00ff00ff, 0xff00ff00,
    };
    unsigned int f, g, j;

    p_ddssel(i);
    ddsinit();

    for(j=0; j<12; j++) {
        f = v[j];
        p_ddswrite(0x0a, f & 0xff);
        p_ddswrite(0x0b, (f >> 8) & 0xff);
        p_ddswrite(0x0c, (f >> 16) & 0xff);
        p_ddswrite(0x0d, (f >> 24) & 0xff);
        p_ddsfud();
        g = p_ddsread(0x0a);
        g |= p_ddsread(0x0b) << 8;
        g |= p_ddsread(0x0c) << 16;
        g |= p_ddsread(0x0d) << 24;
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

static void help(void)
{
    puts("ARTIQ DDS/TTL Tester");
    puts("Available commands:");
    puts("help           - this message");
    puts("clksrc <n>     - select RTIO clock source");
    puts("ttlout <n> <v> - output TTL");
    puts("ddssel <n>     - select a DDS");
    puts("ddsinit        - reset, config, FUD DDS");
    puts("ddsreset       - reset DDS");
    puts("ddsw <a> <d>   - write to DDS register");
    puts("ddsr <a>       - read DDS register");
    puts("ddsfud         - pulse FUD");
    puts("ddsftw <n> <d> - write FTW");
    puts("ddstest <n>    - perform test sequence on DDS");
    puts("leds <n>       - set LEDs");
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

    else if(strcmp(token, "ttlout") == 0) ttlout(get_token(&c), get_token(&c));

    else if(strcmp(token, "ddssel") == 0) ddssel(get_token(&c));
    else if(strcmp(token, "ddsw") == 0) ddsw(get_token(&c), get_token(&c));
    else if(strcmp(token, "ddsr") == 0) ddsr(get_token(&c));
    else if(strcmp(token, "ddsreset") == 0) ddsreset();
    else if(strcmp(token, "ddsinit") == 0) ddsinit();
    else if(strcmp(token, "ddsfud") == 0) ddsfud();
    else if(strcmp(token, "ddsftw") == 0) ddsftw(get_token(&c), get_token(&c));
    else if(strcmp(token, "ddstest") == 0) ddstest(get_token(&c));

    else if(strcmp(token, "") != 0)
        printf("Command not found\n");
}

void test_main(void)
{
    char buffer[64];

#ifdef ARTIQ_AMP
    amp_bridge_init();
#endif

    while(1) {
        putsnonl("\e[1mtest>\e[0m ");
        readstr(buffer, 64);
        do_command(buffer);
    }
}
