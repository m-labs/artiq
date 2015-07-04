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
    MONINJ_REQ_MONITOR = 1,
    MONINJ_REQ_TTLSET = 2
};

enum {
    MONINJ_TTL_MODE_EXP = 0,
    MONINJ_TTL_MODE_1 = 1,
    MONINJ_TTL_MODE_0 = 2,
    MONINJ_TTL_MODE_IN = 3
};

enum {
    MONINJ_TTL_OVERRIDE_ENABLE = 0,
    MONINJ_TTL_OVERRIDE_O = 1,
    MONINJ_TTL_OVERRIDE_OE = 2
};

static struct udp_pcb *listen_pcb;

struct monitor_reply {
    long long int ttl_levels;
    long long int ttl_oes;
    long long int ttl_overrides;
    unsigned int dds_ftws[DDS_CHANNEL_COUNT];
};

static void moninj_monitor(const ip_addr_t *addr, u16_t port)
{
    struct monitor_reply reply;
    int i;
    struct pbuf *reply_p;

    reply.ttl_levels = 0;
    reply.ttl_oes = 0;
    reply.ttl_overrides = 0;
    for(i=0;i<RTIO_REGULAR_TTL_COUNT;i++) {
        rtio_moninj_mon_chan_sel_write(i);
        rtio_moninj_mon_probe_sel_write(0);
        rtio_moninj_mon_value_update_write(1);
        if(rtio_moninj_mon_value_read())
            reply.ttl_levels |= 1LL << i;
        rtio_moninj_mon_probe_sel_write(1);
        rtio_moninj_mon_value_update_write(1);
        if(rtio_moninj_mon_value_read())
            reply.ttl_oes |= 1LL << i;
        rtio_moninj_inj_chan_sel_write(i);
        rtio_moninj_inj_override_sel_write(MONINJ_TTL_OVERRIDE_ENABLE);
        if(rtio_moninj_inj_value_read())
            reply.ttl_overrides |= 1LL << i;
    }

    rtio_moninj_mon_chan_sel_write(RTIO_DDS_CHANNEL);
    for(i=0;i<DDS_CHANNEL_COUNT;i++) {
        rtio_moninj_mon_probe_sel_write(i);
        rtio_moninj_mon_value_update_write(1);
        reply.dds_ftws[i] = rtio_moninj_mon_value_read();
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

static void moninj_ttlset(int channel, int mode)
{
    rtio_moninj_inj_chan_sel_write(channel);
    switch(mode) {
        case MONINJ_TTL_MODE_EXP:
            rtio_moninj_inj_override_sel_write(MONINJ_TTL_OVERRIDE_ENABLE);
            rtio_moninj_inj_value_write(0);
            break;
        case MONINJ_TTL_MODE_1:
            rtio_moninj_inj_override_sel_write(MONINJ_TTL_OVERRIDE_O);
            rtio_moninj_inj_value_write(1);
            rtio_moninj_inj_override_sel_write(MONINJ_TTL_OVERRIDE_OE);
            rtio_moninj_inj_value_write(1);
            rtio_moninj_inj_override_sel_write(MONINJ_TTL_OVERRIDE_ENABLE);
            rtio_moninj_inj_value_write(1);
            break;
        case MONINJ_TTL_MODE_0:
            rtio_moninj_inj_override_sel_write(MONINJ_TTL_OVERRIDE_O);
            rtio_moninj_inj_value_write(0);
            rtio_moninj_inj_override_sel_write(MONINJ_TTL_OVERRIDE_OE);
            rtio_moninj_inj_value_write(1);
            rtio_moninj_inj_override_sel_write(MONINJ_TTL_OVERRIDE_ENABLE);
            rtio_moninj_inj_value_write(1);
            break;
        case MONINJ_TTL_MODE_IN:
            rtio_moninj_inj_override_sel_write(MONINJ_TTL_OVERRIDE_OE);
            rtio_moninj_inj_value_write(0);
            rtio_moninj_inj_override_sel_write(MONINJ_TTL_OVERRIDE_ENABLE);
            rtio_moninj_inj_value_write(1);
            break;
        default:
            log("unknown TTL mode %d", mode);
            break;
    }
}

static void moninj_recv(void *arg, struct udp_pcb *upcb, struct pbuf *req,
                        const ip_addr_t *addr, u16_t port)
{
    char *p = (char *)req->payload;

    if(req->len >= 1) {
        switch(p[0]) {
            case MONINJ_REQ_MONITOR:
                moninj_monitor(addr, port);
                break;
            case MONINJ_REQ_TTLSET:
                if(req->len < 3)
                    break;
                moninj_ttlset(p[1], p[2]);
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
