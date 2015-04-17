// This file is Copyright (c) 2015 Florent Kermarrec <florent@enjoy-digital.fr>
// LiteETH lwIP port for ARTIQ
// License: BSD

#ifndef __LWIPOPTS_H__
#define __LWIPOPTS_H__

//#define LWIP_DEBUG
#include <lwip/debug.h>

/*----------------------------General options ------------------------------ */
#define NO_SYS                  1
#define LWIP_NETCONN            0
#define LWIP_SOCKET             0
#define LWIP_IPV6               0

 /* ------------------------ Memory options -------------------------------- */
/* MEM_ALIGNMENT: should be set to the alignment of the CPU for which
   lwIP is compiled. 4 byte alignment -> define MEM_ALIGNMENT to 4, 2
   byte alignment -> define MEM_ALIGNMENT to 2. */
#define MEM_ALIGNMENT           4     /* MUST BE 4 */

/* MEM_SIZE: the size of the heap memory. If the application will send
a lot of data that needs to be copied, this should be set high. */
#define MEM_SIZE                16000

/* MEMP_NUM_PBUF: the number of memp struct pbufs. If the application
   sends a lot of data out of ROM (or other static memory), this
   should be set high. */
#define MEMP_NUM_PBUF           20
/* MEMP_NUM_UDP_PCB: the number of UDP protocol control blocks. One
   per active UDP "connection". */
#define MEMP_NUM_UDP_PCB        4
/* MEMP_NUM_TCP_PCB: the number of simulatenously active TCP
   connections. */
#define MEMP_NUM_TCP_PCB        10
/* MEMP_NUM_TCP_PCB_LISTEN: the number of listening TCP
   connections. */
#define MEMP_NUM_TCP_PCB_LISTEN 8
/* MEMP_NUM_TCP_SEG: the number of simultaneously queued TCP
   segments. */
#define MEMP_NUM_TCP_SEG        8
/* MEMP_NUM_SYS_TIMEOUT: the number of simulateously active
   timeouts. */
#define MEMP_NUM_SYS_TIMEOUT    3

/* The following four are used only with the sequential API and can be
   set to 0 if the application only will use the raw API. */
/* MEMP_NUM_NETBUF: the number of struct netbufs. */
//#define MEMP_NUM_NETBUF         4
/* MEMP_NUM_NETCONN: the number of struct netconns. */
//#define MEMP_NUM_NETCONN        4

/* These two control is reclaimer functions should be compiled
   in. Should always be turned on (1). */
#define MEM_RECLAIM             1
#define MEMP_RECLAIM            1

/* ---------- Pbuf options ---------- */
/* PBUF_POOL_SIZE: the number of buffers in the pbuf pool. */
#define PBUF_POOL_SIZE          4

/* PBUF_POOL_BUFSIZE: the size of each pbuf in the pbuf pool. */
#define PBUF_POOL_BUFSIZE       1024

/* PBUF_LINK_HLEN: the number of bytes that should be allocated for a
   link level header. */
#define PBUF_LINK_HLEN          16

/* ------------------------ TCP options ----------------------------------- */
#define LWIP_TCP                1
#define TCP_TTL                 255

/* Controls if TCP should queue segments that arrive out of
   order. Define to 0 if your device is low on memory. */
#define TCP_QUEUE_OOSEQ         1

/* TCP Maximum segment size. */
#define TCP_MSS                 256

/* TCP sender buffer space (bytes). */
#define TCP_SND_BUF             512

/* TCP sender buffer space (pbufs). This must be at least = 2 *
   TCP_SND_BUF/TCP_MSS for things to work. */
#define TCP_SND_QUEUELEN        4 * TCP_SND_BUF/TCP_MSS

/* TCP receive window. */
#define TCP_WND                 256

/* Maximum number of retransmissions of data segments. */
#define TCP_MAXRTX              12

/* Maximum number of retransmissions of SYN segments. */
#define TCP_SYNMAXRTX           4

/* ------------------------ ARP options ----------------------------------- */
#define LWIP_ARP                1
#define ARP_TABLE_SIZE          10
#define ARP_QUEUEING            1

/* ------------------------ IP options ------------------------------------ */
/* Define IP_FORWARD to 1 if you wish to have the ability to forward
   IP packets across network interfaces. If you are going to run lwIP
   on a device with only one network interface, define this to 0. */
#define IP_FORWARD              0

/* If defined to 1, IP options are allowed (but not parsed). If
   defined to 0, all packets with IP options are dropped. */
#define IP_OPTIONS              0   /* set it to 1 to allow IP options in hdr */
#define IP_REASSEMBLY           0   /* set it to 1 to enable tcp/ip reassembly */
#define IP_FRAG                 0   /* Outgoing fragmentation of IP packets occurs
                                     * when the packet-size exceeds the path maximum
                                     * packet-size (path MTU).  To avoid fragmentation,
                                     * don't allow application OR lwIP to generate packets larger
                                     * than anticipated path maximum transmission unit.
                                     *
                                     * For TCP, setting TCP_MSS to much less than anticipated
                                     * path MTU avoids frag/defrag.  For UDP it depends on app
                                     * and path MTU.  For ping (ICMP), with large payload,
                                     * frag/reass is required.  Some network stacks have
                                     * path MTU discovery capability but not sure if LwIP
                                     * supports it
                                     */
#define LWIP_RAW                1   /* set it to 1 to enable raw support */

/* ------------------------ ICMP options ---------------------------------- */
#define ICMP_TTL                255

/* ------------------------ DHCP options ---------------------------------- */
/* Define LWIP_DHCP to 1 if you want DHCP configuration of
   interfaces. DHCP is not implemented in lwIP 0.5.1, however, so
   turning this on does currently not work. */
#define LWIP_DHCP               0

/* 1 if you want to do an ARP check on the offered address
   (recommended). */
//#define DHCP_DOES_ARP_CHECK     1

/* ------------------------ UDP options ----------------------------------- */
#define LWIP_UDP                1     /* set it to 1 to enable UDP */
#define UDP_TTL                 255   /* time to live for udp */
#define CHECKSUM_GEN_UDP        0     /* don't generate UDP chksum, if UDP enabled*/
#define CHECKSUM_CHECK_UDP      0     /* check chksum in rx UDP pkts if enabled */

#define LWIP_STATS              0
#define LWIP_COMPAT_SOCKETS     0

/* Override the default dynamic memory alloc functions (malloc copy)*/
//#include "memmgr.h"

//#define mem_init()
//#define mem_free                    memmgr_free
//#define mem_malloc                  memmgr_alloc
//#define mem_calloc(c, n)            memmgr_alloc((c) * (n))
//#define mem_realloc(p, sz)          (p)

#ifdef LWIP_DEBUG
/*
 * for a list of options for the flags, please refer to
 * lwip/src/include/lwip/debug.h
 ******************NOTE********************************
 *
 * TO TURN OFF A SPECIFIC DEBUG SOURCE, SET THE VALUE TO
 *   DBG_OFF
 *
 * DO NOT MODIFY DBG_TYPES_ON OR DBG_MIN_LEVEL UNLESS YOU
 * ARE AWARE WHAT YOU'RE DOING!!
 *
 */
#define LWIP_DBG_TYPES_ON               LWIP_DBG_ON
#define DBG_TYPES_ON                    LWIP_DBG_TRACE

#define LWIP_DBG_MIN_LEVEL              LWIP_DBG_LEVEL_ALL
#define ETHARP_DEBUG                    LWIP_DBG_ON|LWIP_DBG_TRACE
#define NETIF_DEBUG                     LWIP_DBG_ON|LWIP_DBG_TRACE
#define PBUF_DEBUG                      LWIP_DBG_ON|LWIP_DBG_TRACE
#define API_LIB_DEBUG                   LWIP_DBG_ON|LWIP_DBG_TRACE
#define API_MSG_DEBUG                   LWIP_DBG_ON|LWIP_DBG_TRACE
#define SOCKETS_DEBUG                   LWIP_DBG_ON|LWIP_DBG_TRACE
#define ICMP_DEBUG                      LWIP_DBG_ON|LWIP_DBG_TRACE
#define INET_DEBUG                      LWIP_DBG_ON|LWIP_DBG_TRACE
#define IP_DEBUG                        LWIP_DBG_ON|LWIP_DBG_TRACE
#define IP_REASS_DEBUG                  LWIP_DBG_ON|LWIP_DBG_TRACE
#define RAW_DEBUG                       LWIP_DBG_ON|LWIP_DBG_TRACE
#define MEM_DEBUG                       LWIP_DBG_ON|LWIP_DBG_TRACE
#define MEMP_DEBUG                      LWIP_DBG_ON|LWIP_DBG_TRACE
#define SYS_DEBUG                       LWIP_DBG_ON|LWIP_DBG_TRACE
#define TCP_DEBUG                       LWIP_DBG_ON|LWIP_DBG_TRACE
#define TCP_INPUT_DEBUG                 LWIP_DBG_ON|LWIP_DBG_TRACE
#define TCP_FR_DEBUG                    LWIP_DBG_ON|LWIP_DBG_TRACE
#define TCP_RTO_DEBUG                   LWIP_DBG_ON|LWIP_DBG_TRACE
#define TCP_CWND_DEBUG                  LWIP_DBG_ON|LWIP_DBG_TRACE
#define TCP_WND_DEBUG                   LWIP_DBG_ON|LWIP_DBG_TRACE
#define TCP_OUTPUT_DEBUG                LWIP_DBG_ON|LWIP_DBG_TRACE
#define TCP_RST_DEBUG                   LWIP_DBG_ON|LWIP_DBG_TRACE
#define TCP_QLEN_DEBUG                  LWIP_DBG_ON|LWIP_DBG_TRACE
#define UDP_DEBUG                       LWIP_DBG_ON|LWIP_DBG_TRACE
#define TCPIP_DEBUG                     LWIP_DBG_ON|LWIP_DBG_TRACE
#define PPP_DEBUG                       LWIP_DBG_ON|LWIP_DBG_TRACE
#define SLIP_DEBUG                      LWIP_DBG_ON|LWIP_DBG_TRACE
#define DHCP_DEBUG                      LWIP_DBG_ON|LWIP_DBG_TRACE
#define TIMERS_DEBUG                    LWIP_DBG_ON|LWIP_DBG_TRACE

/* APPLICATION DEBUGGING */
/* #define HTTPD_DEBUG                     (1) */
#endif


/* Perform DHCP */
/*#define LWIP_DHCP (1)*/

#endif /* __LWIPOPTS_H__ */
