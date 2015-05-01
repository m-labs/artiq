#include <generated/csr.h>

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

#include "session.h"
#include "kserver.h"

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

void kserver_init(void)
{
    listen_pcb = tcp_new();
    tcp_bind(listen_pcb, IP_ADDR_ANY, 1381);
    listen_pcb = tcp_listen(listen_pcb);
    tcp_accept(listen_pcb, kserver_accept);
}

extern struct tcp_pcb *tcp_active_pcbs;

void kserver_service(void)
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
        if(len < 0)
            kserver_close(active_cs, active_pcb);
    }
}

#endif /* CSR_ETHMAC_BASE */
