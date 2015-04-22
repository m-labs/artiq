#include <stdio.h>
#include <string.h>
#include <irq.h>
#include <uart.h>
#include <console.h>
#include <system.h>
#include <time.h>
#include <generated/csr.h>
#include <hw/flags.h>

#ifdef CSR_ETHMAC_BASE
#include <netif/etharp.h>
#include <netif/liteethif.h>
#include <lwip/init.h>
#include <lwip/memp.h>
#include <lwip/ip4_addr.h>
#include <lwip/ip4.h>
#include <lwip/netif.h>
#include <lwip/sys.h>
#include <lwip/tcp.h>
#include <lwip/timers.h>
#endif

#include "test_mode.h"
#include "session.h"

#ifdef CSR_ETHMAC_BASE
unsigned char macadr[6] = {0x10, 0xe2, 0xd5, 0x00, 0x00, 0x00};

u32_t clock_ms;

static void clock_init(void)
{
    timer0_en_write(0);
    timer0_load_write(0xffffffff);
    timer0_reload_write(0xffffffff);
    timer0_en_write(1);
    clock_ms = 0;
}

u32_t sys_now(void)
{
    unsigned int freq;
    unsigned int prescaler;

    freq = identifier_frequency_read();
    prescaler = freq/1000; /* sys_now expect time in ms */
    timer0_update_value_write(1);
    clock_ms += (0xffffffff - timer0_value_read())/prescaler;
    /* Reset timer to avoid rollover, this will increase clock_ms
       drift but we don't need precision */
    timer0_en_write(0);
    timer0_en_write(1);
    return clock_ms;
}

static struct netif netif;

static void lwip_service(void)
{
    sys_check_timeouts();
    if(ethmac_sram_writer_ev_pending_read() & ETHMAC_EV_SRAM_WRITER) {
        liteeth_input(&netif);
        ethmac_sram_writer_ev_pending_write(ETHMAC_EV_SRAM_WRITER);
    }
}
#endif

void comm_service(void)
{
    char *txdata;
    int txlen;
    static char rxdata;
    static int rxpending;
    int r, i;

#ifdef CSR_ETHMAC_BASE
        lwip_service();
#endif

    if(!rxpending && uart_read_nonblock()) {
        rxdata = uart_read();
        rxpending = 1;
    }
    if(rxpending) {
        r = session_input(&rxdata, 1);
        if(r > 0)
            rxpending = 0;
    }

    session_poll((void **)&txdata, &txlen);
    if(txlen > 0) {
        for(i=0;i<txlen;i++)
            uart_write(txdata[i]);
        session_ack(txlen);
    }
}

static void regular_main(void)
{
#ifdef CSR_ETHMAC_BASE
    struct ip4_addr local_ip;
    struct ip4_addr netmask;
    struct ip4_addr gateway_ip;

    time_init();
    clock_init();

    IP4_ADDR(&local_ip, 192, 168, 0, 42);
    IP4_ADDR(&netmask, 255, 255, 255, 0);
    IP4_ADDR(&gateway_ip, 192, 168, 0, 1);

    lwip_init();

    netif_add(&netif, &local_ip, &netmask, &gateway_ip, 0, liteeth_init, ethernet_input);
    netif_set_default(&netif);
    netif_set_up(&netif);
    netif_set_link_up(&netif);
#endif

    session_start();
    while(1)
        comm_service();
}


static void blink_led(void)
{
    int i, ev, p;

    p = identifier_frequency_read()/10;
    time_init();
    for(i=0;i<3;i++) {
        leds_out_write(1);
        while(!elapsed(&ev, p));
        leds_out_write(0);
        while(!elapsed(&ev, p));
    }
}

static int check_test_mode(void)
{
    char c;

    timer0_en_write(0);
    timer0_reload_write(0);
    timer0_load_write(identifier_frequency_read() >> 2);
    timer0_en_write(1);
    timer0_update_value_write(1);
    while(timer0_value_read()) {
        if(readchar_nonblock()) {
            c = readchar();
            if((c == 't')||(c == 'T'))
                return 1;
        }
        timer0_update_value_write(1);
    }
    return 0;
}

int main(void)
{
    irq_setmask(0);
    irq_setie(1);
    uart_init();

#ifdef ARTIQ_AMP
    puts("ARTIQ runtime built "__DATE__" "__TIME__" for AMP systems\n");
#else
    puts("ARTIQ runtime built "__DATE__" "__TIME__" for UP systems\n");
#endif
    blink_led();

    if(check_test_mode()) {
        puts("Entering test mode.");
        test_main();
    } else {
        puts("Entering regular mode.");
        regular_main();
    }
    return 0;
}
