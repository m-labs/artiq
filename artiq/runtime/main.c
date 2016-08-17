#include <stdio.h>
#include <string.h>
#include <alloc.h>
#include <irq.h>
#include <uart.h>
#include <console.h>
#include <system.h>
#include <generated/csr.h>
#include <hw/flags.h>

#include <lwip/init.h>
#include <lwip/memp.h>
#include <lwip/ip4_addr.h>
#include <lwip/ip4.h>
#include <lwip/netif.h>
#include <lwip/sys.h>
#include <lwip/tcp.h>
#include <lwip/timers.h>
#ifdef CSR_ETHMAC_BASE
#include <netif/etharp.h>
#include <liteethif.h>
#else
#include <netif/ppp/ppp.h>
#include <netif/ppp/pppos.h>
#endif

#include "bridge_ctl.h"
#include "kloader.h"
#include "flash_storage.h"
#include "clock.h"
#include "rtiocrg.h"
#include "test_mode.h"
#include "net_server.h"
#include "session.h"
#include "analyzer.h"
#include "moninj.h"

u32_t sys_now(void)
{
    return clock_get_ms();
}

u32_t sys_jiffies(void)
{
    return clock_get_ms();
}

static struct netif netif;

#ifndef CSR_ETHMAC_BASE
static ppp_pcb *ppp;
#endif

static void lwip_service(void)
{
    sys_check_timeouts();
#ifdef CSR_ETHMAC_BASE
    liteeth_input(&netif);
#else
    if(uart_read_nonblock()) {
        u8_t c;
        c = uart_read();
        pppos_input(ppp, &c, 1);
    }
#endif
}

#ifdef CSR_ETHMAC_BASE
unsigned char macadr[6];

static int hex2nib(int c)
{
    if((c >= '0') && (c <= '9'))
        return c - '0';
    if((c >= 'a') && (c <= 'f'))
        return c - 'a' + 10;
    if((c >= 'A') && (c <= 'F'))
        return c - 'A' + 10;
    return -1;
}

static void init_macadr(void)
{
    static const unsigned char default_macadr[6] = {0x10, 0xe2, 0xd5, 0x32, 0x50, 0x00};
#if (defined CSR_SPIFLASH_BASE && defined CONFIG_SPIFLASH_PAGE_SIZE)
    char b[32];
    char fs_macadr[6];
    int i, r, s;
#endif

    memcpy(macadr, default_macadr, 6);
#if (defined CSR_SPIFLASH_BASE && defined CONFIG_SPIFLASH_PAGE_SIZE)
    r = fs_read("mac", b, sizeof(b) - 1, NULL);
    if(r <= 0)
        return;
    b[r] = 0;
    for(i=0;i<6;i++) {
        r = hex2nib(b[3*i]);
        s = hex2nib(b[3*i + 1]);
        if((r < 0) || (s < 0))
            return;
        fs_macadr[i] = (r << 4) | s;
    }
    for(i=0;i<5;i++)
        if(b[3*i + 2] != ':')
            return;
    memcpy(macadr, fs_macadr, 6);
#endif
}

static void fsip_or_default(struct ip4_addr *d, char *key, int i1, int i2, int i3, int i4)
{
    int r;
#if (defined CSR_SPIFLASH_BASE && defined CONFIG_SPIFLASH_PAGE_SIZE)
    char cp[32];
#endif

    IP4_ADDR(d, i1, i2, i3, i4);
#if (defined CSR_SPIFLASH_BASE && defined CONFIG_SPIFLASH_PAGE_SIZE)
    r = fs_read(key, cp, sizeof(cp) - 1, NULL);
    if(r <= 0)
        return;
    cp[r] = 0;
    if(!ip4addr_aton(cp, d))
        return;
#endif
}

static void network_init(void)
{
    struct ip4_addr local_ip;
    struct ip4_addr netmask;
    struct ip4_addr gateway_ip;

    init_macadr();
    fsip_or_default(&local_ip, "ip", 192, 168, 1, 50);
    fsip_or_default(&netmask, "netmask", 255, 255, 255, 0);
    fsip_or_default(&gateway_ip, "gateway", 192, 168, 1, 1);

    lwip_init();

    netif_add(&netif, &local_ip, &netmask, &gateway_ip, 0, liteeth_init, ethernet_input);
    netif_set_default(&netif);
    netif_set_up(&netif);
    netif_set_link_up(&netif);
}
#else /* CSR_ETHMAC_BASE */

static int ppp_connected;

static u32_t ppp_output_cb(ppp_pcb *pcb, u8_t *data, u32_t len, void *ctx)
{
    for(int i = 0; i < len; i++)
        uart_write(data[i]);
    return len;
}

static void ppp_status_cb(ppp_pcb *pcb, int err_code, void *ctx)
{
    if (err_code == PPPERR_NONE) {
        ppp_connected = 1;
        return;
    } else if (err_code == PPPERR_USER) {
        return;
    } else {
        ppp_connect(pcb, 1);
    }
}

static void network_init(void)
{
    lwip_init();

    ppp_connected = 0;
    ppp = pppos_create(&netif, ppp_output_cb, ppp_status_cb, NULL);
    ppp_set_auth(ppp, PPPAUTHTYPE_NONE, "", "");
    ppp_set_default(ppp);
    ppp_connect(ppp, 0);

    while (!ppp_connected)
        lwip_service();
}

#endif /* CSR_ETHMAC_BASE */


static struct net_server_instance session_inst = {
    .port = 1381,
    .start = session_start,
    .end = session_end,
    .input = session_input,
    .poll = session_poll,
    .ack_consumed = session_ack_consumed,
    .ack_sent = session_ack_sent
};

#ifdef CSR_RTIO_ANALYZER_BASE
static struct net_server_instance analyzer_inst = {
    .port = 1382,
    .start = analyzer_start,
    .end = analyzer_end,
    .input = analyzer_input,
    .poll = analyzer_poll,
    .ack_consumed = analyzer_ack_consumed,
    .ack_sent = analyzer_ack_sent
};
#endif

static void regular_main(void)
{
    puts("Accepting network sessions.");
    network_init();
    net_server_init(&session_inst);
#ifdef CSR_RTIO_ANALYZER_BASE
    analyzer_init();
    net_server_init(&analyzer_inst);
#endif
    moninj_init();

    session_end();
    while(1) {
        lwip_service();
        kloader_service_essential_kmsg();
        net_server_service();
    }
}

static void blink_led(void)
{
    int i;
    long long int t;

    for(i=0;i<3;i++) {
#ifdef CSR_LEDS_BASE
        leds_out_write(1);
#endif
        t = clock_get_ms();
        while(clock_get_ms() < t + 250);
#ifdef CSR_LEDS_BASE
        leds_out_write(0);
#endif
        t = clock_get_ms();
        while(clock_get_ms() < t + 250);
    }
}

static int check_test_mode(void)
{
    char c;
    long long int t;

    t = clock_get_ms();
    while(clock_get_ms() < t + 1000) {
        if(readchar_nonblock()) {
            c = readchar();
            if((c == 't')||(c == 'T'))
                return 1;
        }
    }
    return 0;
}

extern void _fheap, _eheap;

extern void rust_main();

int main(void)
{
    irq_setmask(0);
    irq_setie(1);
    uart_init();

    puts("ARTIQ runtime built "__DATE__" "__TIME__"\n");

    alloc_give(&_fheap, &_eheap - &_fheap);
    clock_init();
    rtiocrg_init();
    puts("Press 't' to enter test mode...");
    blink_led();

    puts("Calling Rust...");
    rust_main();

    if(check_test_mode()) {
        puts("Entering test mode.");
        test_main();
    } else {
        puts("Entering regular mode.");
        session_startup_kernel();
        regular_main();
    }
    return 0;
}
