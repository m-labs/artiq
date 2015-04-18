// This file is Copyright (c) 2015 Florent Kermarrec <florent@enjoy-digital.fr>
// LiteETH lwIP port for ARTIQ
// License: BSD

#include <generated/csr.h>

#ifdef CSR_ETHMAC_BASE

#include <lwip/opt.h>
#include <lwip/mem.h>

#include <netif/etharp.h>
#include "netif/liteethif.h"

#include <hw/flags.h>
#include <hw/ethmac_mem.h>

typedef union {
    unsigned char raw[1514];
} ethernet_buffer;

static unsigned int rxslot;
static unsigned int rxlen;
static ethernet_buffer *rxbuffer;
static ethernet_buffer *rxbuffer0;
static ethernet_buffer *rxbuffer1;
static unsigned int txslot;
static unsigned int txlen;
static ethernet_buffer *txbuffer;
static ethernet_buffer *txbuffer0;
static ethernet_buffer *txbuffer1;

#define IFNAME0 'e'
#define IFNAME1 't'

static void liteeth_low_level_init(struct netif *netif)
{
    int i;

    netif->hwaddr_len = 6;
    for(i=0;i<netif->hwaddr_len;i++)
    netif->hwaddr[i] = macadr[i];
    netif->mtu = 1514;
    netif->flags = NETIF_FLAG_BROADCAST | NETIF_FLAG_ETHARP;

    ethmac_sram_reader_ev_pending_write(ETHMAC_EV_SRAM_READER);
    ethmac_sram_writer_ev_pending_write(ETHMAC_EV_SRAM_WRITER);

    rxbuffer0 = (ethernet_buffer *)ETHMAC_RX0_BASE;
    rxbuffer1 = (ethernet_buffer *)ETHMAC_RX1_BASE;
    txbuffer0 = (ethernet_buffer *)ETHMAC_TX0_BASE;
    txbuffer1 = (ethernet_buffer *)ETHMAC_TX1_BASE;

    rxslot = 0;
    txslot = 0;

    rxbuffer = rxbuffer0;
    txbuffer = txbuffer0;
}

static err_t liteeth_low_level_output(struct netif *netif, struct pbuf *p)
{
    struct pbuf *q;

    txlen = 0;
    for(q = p; q != NULL; q = q->next) {
        memcpy(txbuffer->raw, q->payload, q->len);
        txbuffer += q->len;
        txlen += q->len;
    }

    ethmac_sram_reader_slot_write(txslot);
    ethmac_sram_reader_length_write(txlen);
    while(!ethmac_sram_reader_ready_read());
    ethmac_sram_reader_start_write(1);

    txslot = (txslot + 1) % 2;
    if(txslot)
        txbuffer = txbuffer1;
    else
        txbuffer = txbuffer0;

    return ERR_OK;
}

static struct pbuf *liteeth_low_level_input(struct netif *netif)
{
    struct pbuf *p, *q;

    rxslot = ethmac_sram_writer_slot_read();
    rxlen = ethmac_sram_writer_length_read();
    if(rxslot)
        rxbuffer = rxbuffer1;
    else
      rxbuffer = rxbuffer0;

    p = pbuf_alloc(PBUF_RAW, rxlen, PBUF_POOL);
    if(p != NULL) {
        for(q = p; q != NULL; q = q->next) {
           memcpy(q->payload, rxbuffer->raw, q->len);
           rxbuffer += q->len;
        }
    }

    return p;
}

void liteeth_input(struct netif *netif)
{
    struct pbuf *p;
    p = liteeth_low_level_input(netif);
    if(p != NULL)
        netif->input(p, netif);
}

err_t liteeth_init(struct netif *netif)
{
    struct liteethif *liteethif;

    liteethif = mem_malloc(sizeof(struct liteethif));
    if(liteethif == NULL)
        return ERR_MEM;
    netif->state = liteethif;

    netif->hwaddr_len = 6;
    netif->name[0] = IFNAME0;
    netif->name[1] = IFNAME1;
    netif->output = etharp_output;
    netif->linkoutput = liteeth_low_level_output;
    netif->mtu = 1514;

    liteethif->ethaddr = (struct eth_addr *)&(netif->hwaddr[0]);

    liteeth_low_level_init(netif);

    return ERR_OK;
}

#endif /* CSR_ETHMAC_BASE */
