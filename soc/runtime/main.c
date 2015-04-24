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

static int clkdiv;

u32_t sys_now(void)
{
    static unsigned long long int clock_sys;
    u32_t clock_ms;

    timer0_update_value_write(1);
    clock_sys += 0xffffffff - timer0_value_read();
    timer0_en_write(0);
    timer0_en_write(1);

    clock_ms = clock_sys/clkdiv;
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

static void network_init(void)
{
    struct ip4_addr local_ip;
    struct ip4_addr netmask;
    struct ip4_addr gateway_ip;

    timer0_en_write(0);
    timer0_load_write(0xffffffff);
    timer0_reload_write(0xffffffff);
    timer0_en_write(1);
    clkdiv = identifier_frequency_read()/1000;

    IP4_ADDR(&local_ip, 192, 168, 0, 42);
    IP4_ADDR(&netmask, 255, 255, 255, 0);
    IP4_ADDR(&gateway_ip, 192, 168, 0, 1);

    lwip_init();

    netif_add(&netif, &local_ip, &netmask, &gateway_ip, 0, liteeth_init, ethernet_input);
    netif_set_default(&netif);
    netif_set_up(&netif);
    netif_set_link_up(&netif);
}

struct kserver_connstate {
    int magic_recognized;
    struct pbuf *rp;
    int rp_offset;
};

static struct kserver_connstate *cs_new(void)
{
    struct kserver_connstate *cs;

    cs = (struct kserver_connstate *)mem_malloc(sizeof(struct kserver_connstate));
    if(!cs)
        return NULL;
    cs->magic_recognized = 0;
    cs->rp = NULL;
    cs->rp_offset = 0;
    return cs;
}

static void cs_free(struct kserver_connstate *cs)
{
    if(cs->rp)
        pbuf_free(cs->rp);
    mem_free(cs);
}

static const char kserver_magic[] = "ARTIQ coredev\n";

static int magic_ok(struct kserver_connstate *cs)
{
    return cs->magic_recognized >= 14;
}

static struct kserver_connstate *active_cs;
static struct tcp_pcb *active_pcb;

static void kserver_close(struct kserver_connstate *cs, struct tcp_pcb *pcb)
{
    if(cs == active_cs) {
        session_end();
        active_cs = NULL;
        active_pcb = NULL;
    }

    /* lwip loves to call back with broken pointers. Prevent that. */
    tcp_arg(pcb, NULL);
    tcp_recv(pcb, NULL);
    tcp_sent(pcb, NULL);
    tcp_err(pcb, NULL);

    cs_free(cs);
    tcp_close(pcb);
}

static err_t kserver_recv(void *arg, struct tcp_pcb *pcb, struct pbuf *p, err_t err)
{
    struct kserver_connstate *cs;

    cs = (struct kserver_connstate *)arg;
    if(p) {
        if(cs->rp)
            pbuf_cat(cs->rp, p);
        else {
            cs->rp = p;
            cs->rp_offset = 0;
        }
    } else
        kserver_close(cs, pcb);
    return ERR_OK;
}

static err_t kserver_sent(void *arg, struct tcp_pcb *pcb, u16_t len)
{
    session_ack_mem(len);
    return ERR_OK;
}

static void tcp_pcb_service(void *arg, struct tcp_pcb *pcb)
{
    struct kserver_connstate *cs;
    int remaining_in_pbuf;
    char *rpp;
    struct pbuf *next;
    int r;

    cs = (struct kserver_connstate *)arg;

    while(cs->rp) {
        remaining_in_pbuf = cs->rp->len - cs->rp_offset;
        rpp = (char *)cs->rp->payload;
        while(remaining_in_pbuf > 0) {
            if(cs == active_cs) {
                r = session_input(&rpp[cs->rp_offset], remaining_in_pbuf);
                if(r > 0) {
                    tcp_recved(pcb, r);
                    cs->rp_offset += r;
                    remaining_in_pbuf -= r;
                } else if(r == 0)
                    return;
                else
                    kserver_close(cs, pcb);
            } else {
                if(rpp[cs->rp_offset] == kserver_magic[cs->magic_recognized]) {
                    cs->magic_recognized++;
                    if(magic_ok(cs)) {
                        if(active_cs)
                            kserver_close(active_cs, active_pcb);
                        session_start();
                        active_cs = cs;
                        active_pcb = pcb;
                        tcp_sent(pcb, kserver_sent);
                    }
                } else {
                    kserver_close(cs, pcb);
                    return;
                }
                remaining_in_pbuf--;
                cs->rp_offset++;
                tcp_recved(pcb, 1);
            }
        }
        next = cs->rp->next;
        if(cs->rp->tot_len != cs->rp->len) {
            pbuf_ref(next);
            pbuf_free(cs->rp);
            cs->rp = next;
            cs->rp_offset = 0;
        } else {
            pbuf_free(cs->rp);
            cs->rp = NULL;
        }
    }
}

static void kserver_err(void *arg, err_t err)
{
    struct kserver_connstate *cs;

    cs = (struct kserver_connstate *)arg;
    cs_free(cs);
}

static struct tcp_pcb *listen_pcb;

static err_t kserver_accept(void *arg, struct tcp_pcb *newpcb, err_t err)
{
    struct kserver_connstate *cs;

    cs = cs_new();
    if(!cs)
        return ERR_MEM;
    tcp_accepted(listen_pcb);
    tcp_arg(newpcb, cs);
    tcp_recv(newpcb, kserver_recv);
    tcp_err(newpcb, kserver_err);
    return ERR_OK;
}

static void kserver_init(void)
{
    listen_pcb = tcp_new();
    tcp_bind(listen_pcb, IP_ADDR_ANY, 1381);
    listen_pcb = tcp_listen(listen_pcb);
    tcp_accept(listen_pcb, kserver_accept);
}

extern struct tcp_pcb *tcp_active_pcbs;

static void kserver_service(void)
{
    struct tcp_pcb *pcb;
    void *data;
    int len, sndbuf;

    /* Assume all active TCP PCBs with a non-NULL arg are our connections. */
    pcb = tcp_active_pcbs;
    while(pcb) {
        if(pcb->callback_arg)
            tcp_pcb_service(pcb->callback_arg, pcb);
        pcb = pcb->next;
    }

    if(active_cs) {
        session_poll(&data, &len);
        if(len > 0) {
            sndbuf = tcp_sndbuf(active_pcb);
            if(len > sndbuf)
                len = sndbuf;
            tcp_write(active_pcb, data, len, 0);
            session_ack_data(len);
        }
    }
}

static void regular_main(void)
{
    network_init();
    kserver_init();

    while(1) {
        lwip_service();
        kserver_service();
    }
}

#else /* CSR_ETHMAC_BASE */

static void serial_service(void)
{
    char *txdata;
    int txlen;
    static char rxdata;
    static int rxpending;
    int r, i;

    if(!rxpending && uart_read_nonblock()) {
        rxdata = uart_read();
        rxpending = 1;
    }
    if(rxpending) {
        r = session_input(&rxdata, 1);
        if(r > 0)
            rxpending = 0;
        if(r < 0) {
            session_end();
            session_start();
        }
    }

    session_poll((void **)&txdata, &txlen);
    if(txlen > 0) {
        for(i=0;i<txlen;i++)
            uart_write(txdata[i]);
        session_ack_data(txlen);
        session_ack_mem(txlen);
    }
}

static void regular_main(void)
{
    /* Open the session for the serial control. */
    session_start();
    while(1)
        serial_service();
}

#endif

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
#ifdef CSR_ETHMAC_BASE
    puts("Accepting sessions on Ethernet");
#else
    puts("Accepting sessions on serial link");
#endif
    puts("Press 't' to enter test mode...");
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
