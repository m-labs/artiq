include $(MSCDIR)/software/common.mak

OBJECTS := isr.o clock.o rtiocrg.o flash_storage.o mailbox.o \
	session.o log.o moninj.o net_server.o bridge_ctl.o \
	ksupport_data.o kloader.o test_mode.o main.o
OBJECTS_KSUPPORT := ksupport.o artiq_personality.o mailbox.o \
	bridge.o rtio.o ttl.o dds.o

CFLAGS += -I$(MSCDIR)/software/include/dyld \
	-I$(MSCDIR)/software/unwinder/include \
	-I$(MSCDIR)/software/libunwind \
	-Ilwip/src/include -Iliblwip

all: runtime.bin runtime.fbi

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	@chmod -x $@

%.fbi: %.bin
	@echo " MSCIMG  " $@ && $(MSCDIR)/mkmscimg.py -f -o $@ $<

runtime.elf: $(OBJECTS) libs
	$(LD) $(LDFLAGS) \
		-T runtime.ld \
		-N -o $@ \
		$(MSCDIR)/software/libbase/crt0-$(CPU).o \
		$(OBJECTS) \
		-L$(MSCDIR)/software/libbase \
		-L$(MSCDIR)/software/libcompiler-rt \
		-Lliblwip \
		-lbase -lcompiler-rt -llwip
	@chmod -x $@

ksupport.elf: $(OBJECTS_KSUPPORT) libs
	$(LD) $(LDFLAGS) \
		--eh-frame-hdr \
		-T ksupport.ld \
		-N -o $@ \
		$(MSCDIR)/software/libbase/crt0-$(CPU).o \
		$(OBJECTS_KSUPPORT) \
		-L$(MSCDIR)/software/libbase \
		-L$(MSCDIR)/software/libcompiler-rt \
		-L$(MSCDIR)/software/libunwind \
		-L$(MSCDIR)/software/libdyld \
		-lbase -lcompiler-rt -lunwind -ldyld
	@chmod -x $@

ksupport_data.o: ksupport.elf
	$(LD) -r -b binary -o $@ $<

main.o: main.c
	$(compile-dep)

%.o: %.c
	$(compile-dep)

%.o: %.S
	$(assemble)

libs:
	$(MAKE) -C $(MSCDIR)/software/libcompiler-rt
	$(MAKE) -C $(MSCDIR)/software/libunwind
	$(MAKE) -C $(MSCDIR)/software/libbase
	$(MAKE) -C $(MSCDIR)/software/libdyld
	$(MAKE) -C liblwip

clean:
	$(MAKE) -C liblwip clean
	$(RM) $(OBJECTS) $(OBJECTS:.o=.d) $(OBJECTS_KSUPPORT) $(OBJECTS_KSUPPORT:.o=.d)
	$(RM) runtime.elf runtime.bin runtime.fbi .*~ *~
	$(RM) ksupport.elf ksupport.bin

.PHONY: all main.o clean libs load
