include $(MSCDIR)/software/common.mak

LWIPDIR=../lwip/src

CFLAGS += $(CPPFLAGS) -I. \
	-I$(LWIPDIR)/include \
	-I$(LWIPDIR)/include/ipv4

# COREFILES, CORE4FILES: The minimum set of files needed for lwIP.
COREOBJS=$(LWIPDIR)/core/mem.o \
	$(LWIPDIR)/core/memp.o \
	$(LWIPDIR)/core/netif.o \
	$(LWIPDIR)/core/pbuf.o \
	$(LWIPDIR)/core/raw.o \
	$(LWIPDIR)/core/stats.o \
	$(LWIPDIR)/core/sys.o \
	$(LWIPDIR)/core/tcp.o \
	$(LWIPDIR)/core/tcp_in.o \
	$(LWIPDIR)/core/tcp_out.o \
	$(LWIPDIR)/core/udp.o \
	$(LWIPDIR)/core/dhcp.o \
	$(LWIPDIR)/core/inet_chksum.o \
	$(LWIPDIR)/core/timers.o \
	$(LWIPDIR)/core/init.o

CORE4OBJS=$(LWIPDIR)/core/ipv4/icmp.o \
	$(LWIPDIR)/core/ipv4/ip4.o \
	$(LWIPDIR)/core/ipv4/ip4_addr.o \
	$(LWIPDIR)/core/ipv4/ip_frag.o

# NETIFOBJS: Files implementing various generic network interface functions.
NETIFOBJS=$(LWIPDIR)/netif/etharp.o  \
	netif/liteethif.o

# LWIPOBJS: All the above.
LWIPOBJS=$(COREOBJS) $(CORE4OBJS) $(NETIFOBJS)
OBJS_LIB+=$(LWIPOBJS)

LWIPLIB=liblwip.a

all: $(LWIPLIB)

.PHONY: all compile clean

%.o: %.c
	$(compile-dep)

%.o: %.S
	$(assemble)

clean:
	rm -f $(LWIPOBJS) $(LWIPOBJS:.o=.d) $(LWIPLIB)

liblwip.a: $(LWIPOBJS)
	$(AR) clr liblwip.a $(LWIPOBJS)
