include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

LWIPDIR=$(LIBLWIP_DIRECTORY)/../lwip/src

CFLAGS += $(CPPFLAGS) -I. \
	-I$(LWIPDIR)/include \
	-I$(LWIPDIR)/include/ipv4

# COREFILES, CORE4FILES: The minimum set of files needed for lwIP.
COREFILES=core/mem.c \
	core/memp.c \
	core/netif.c \
	core/pbuf.c \
	core/raw.c \
	core/stats.c \
	core/sys.c \
	core/tcp.c \
	core/tcp_in.c \
	core/tcp_out.c \
	core/udp.c \
	core/dhcp.c \
	core/inet_chksum.c \
	core/timers.c \
	core/init.c

CORE4FILES=core/ipv4/icmp.c \
	core/ipv4/ip4.c \
	core/ipv4/ip4_addr.c \
	core/ipv4/ip_frag.c

# NETIFFILES: Files implementing various generic network interface functions.
NETIFFILES=netif/etharp.c

# LWIPFILES: All the above.
LWIPFILES=$(COREFILES) $(CORE4FILES) $(NETIFFILES)

LWIPOBJS:=$(LWIPFILES:.c=.o) liteethif.o

all: prepare liblwip.a

prepare:
	rm -f lwipopts.h
	rm -f arch
	ln -s $(LIBLWIP_DIRECTORY)/lwipopts.h lwipopts.h
	ln -s $(LIBLWIP_DIRECTORY)/arch arch
	mkdir -p core/ipv4
	mkdir -p netif

core/%.o: $(LWIPDIR)/core/%.c
	$(compile)

core/ipv4/%.o: $(LWIPDIR)/core/ipv4/%.c
	$(compile)

netif/%.o: $(LWIPDIR)/netif/%.c
	$(compile)

%.o: $(LIBLWIP_DIRECTORY)/%.c
	$(compile)

.PHONY: all clean prepare

clean:
	rm -f $(LWIPOBJS) liblwip.a

liblwip.a: $(LWIPOBJS)
	$(AR) clr liblwip.a $(LWIPOBJS)
