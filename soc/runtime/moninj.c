#include <generated/csr.h>

#ifdef CSR_ETHMAC_BASE

#include <netif/etharp.h>
#include <lwip/init.h>
#include <lwip/memp.h>
#include <lwip/ip4_addr.h>
#include <lwip/ip4.h>
#include <lwip/netif.h>
#include <lwip/sys.h>
#include <lwip/udp.h>
#include <lwip/timers.h>

#include "log.h"
#include "moninj.h"

enum {
    MONINJ_REQ_MONITOR = 1
};

static struct udp_pcb *listen_pcb;

struct monitor_reply {
    long long int ttl_levels;
    long long int ttl_oes;
};

static void moninj_monitor(const ip_addr_t *addr, u16_t port)
{
    struct monitor_reply reply;
    int i;
    struct pbuf *reply_p;

    reply.ttl_levels = 0;
    reply.ttl_oes = 0;
    for(i=0;i<RTIO_TTL_COUNT;i++) {
        rtio_mon_chan_sel_write(i);
        rtio_mon_probe_sel_write(0);
        if(rtio_mon_probe_value_read())
            reply.ttl_levels |= 1LL << i;
        rtio_mon_probe_sel_write(1);
        if(rtio_mon_probe_value_read())
            reply.ttl_oes |= 1LL << i;
    }

    reply_p = pbuf_alloc(PBUF_TRANSPORT, sizeof(struct monitor_reply), PBUF_RAM);
    if(!reply_p) {
        log("Failed to allocate pbuf for monitor reply");
        return;
    }
    memcpy(reply_p->payload, &reply, sizeof(struct monitor_reply));
    udp_sendto(listen_pcb, reply_p, addr, port);
    pbuf_free(reply_p);
}

static void moninj_recv(void *arg, struct udp_pcb *upcb, struct pbuf *req,
                        const ip_addr_t *addr, u16_t port)
{
    if(req->len >= 1) {
        switch(*(char *)req->payload) {
            case MONINJ_REQ_MONITOR:
                moninj_monitor(addr, port);
                break;
            default:
                break;
        }
    }
    pbuf_free(req); /* beware: addr may point into the req pbuf */
}

void moninj_init(void)
{
    listen_pcb = udp_new();
    if(!listen_pcb) {
        log("Failed to create UDP listening PCB");
        return;
    }
    udp_bind(listen_pcb, IP_ADDR_ANY, 3250);
    udp_recv(listen_pcb, moninj_recv, NULL);
}

#endif /* CSR_ETHMAC_BASE */
