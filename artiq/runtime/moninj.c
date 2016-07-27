#include <generated/csr.h>

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
    unsigned short int dds_rtio_first_channel;
    unsigned short int dds_channels_per_bus;
#if ((defined RTIO_DDS_COUNT) && (RTIO_DDS_COUNT > 0))
    unsigned int dds_ftws[CONFIG_RTIO_DDS_COUNT*CONFIG_DDS_CHANNELS_PER_BUS];
#endif
} __attribute__((packed));

static void moninj_monitor(const ip_addr_t *addr, u16_t port)
{
    struct monitor_reply reply;
    int i;
    struct pbuf *reply_p;

    reply.ttl_levels = 0;
    reply.ttl_oes = 0;
    reply.ttl_overrides = 0;
    for(i=0;i<CONFIG_RTIO_REGULAR_TTL_COUNT;i++) {
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

#if ((defined RTIO_DDS_COUNT) && (RTIO_DDS_COUNT > 0))
    int j;

    reply.dds_rtio_first_channel = CONFIG_RTIO_FIRST_DDS_CHANNEL;
    reply.dds_channels_per_bus = CONFIG_DDS_CHANNELS_PER_BUS;
    for(j=0;j<CONFIG_RTIO_DDS_COUNT;j++) {
        rtio_moninj_mon_chan_sel_write(CONFIG_RTIO_FIRST_DDS_CHANNEL+j);
        for(i=0;i<CONFIG_DDS_CHANNELS_PER_BUS;i++) {
            rtio_moninj_mon_probe_sel_write(i);
            rtio_moninj_mon_value_update_write(1);
            reply.dds_ftws[CONFIG_DDS_CHANNELS_PER_BUS*j+i] = rtio_moninj_mon_value_read();
        }
    }
#else
    reply.dds_rtio_first_channel = 0;
    reply.dds_channels_per_bus = 0;
#endif

    reply_p = pbuf_alloc(PBUF_TRANSPORT, sizeof(struct monitor_reply), PBUF_RAM);
    if(!reply_p) {
        core_log("Failed to allocate pbuf for monitor reply\n");
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
            core_log("unknown TTL mode %d\n", mode);
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
        core_log("Failed to create UDP listening PCB\n");
        return;
    }
    udp_bind(listen_pcb, IP_ADDR_ANY, 3250);
    udp_recv(listen_pcb, moninj_recv, NULL);
}
