// This file is Copyright (c) 2015 Florent Kermarrec <florent@enjoy-digital.fr>
// LiteETH lwIP port for ARTIQ
// License: BSD

#ifndef __LITEETHIF_H__
#define __LITEETHIF_H__

extern unsigned char macadr[];

void liteeth_input(struct netif *netif);
err_t liteeth_init(struct netif *netif);

#endif /* __LITEETH_IF_H__ */
