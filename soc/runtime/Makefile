include $(MSCDIR)/software/common.mak

OBJECTS := isr.o flash_storage.o clock.o rtiocrg.o elf_loader.o services.o session.o log.o test_mode.o kloader.o bridge_ctl.o mailbox.o ksupport_data.o net_server.o moninj.o main.o
OBJECTS_KSUPPORT := ksupport.o exception_jmp.o exceptions.o mailbox.o bridge.o rtio.o ttl.o dds.o

CFLAGS += -Ilwip/src/include -Iliblwip

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
		-T linker.ld \
		-N -o $@ \
		$(MSCDIR)/software/libbase/crt0-$(CPU).o \
		$(OBJECTS) \
		-L$(MSCDIR)/software/libbase \
		-L$(MSCDIR)/software/libcompiler-rt \
		-Lliblwip \
		-lbase -lcompiler-rt -llwip
	@chmod -x $@

ksupport.elf: $(OBJECTS_KSUPPORT)
	$(LD) $(LDFLAGS) \
		-T ksupport.ld \
		-N -o $@ \
		$(MSCDIR)/software/libbase/crt0-$(CPU).o \
		$^ \
		-L$(MSCDIR)/software/libcompiler-rt \
		-lcompiler-rt
	@chmod -x $@

ksupport_data.o: ksupport.bin
	$(LD) -r -b binary -o $@ $<

service_table.h: ksupport.elf gen_service_table.py
	@echo " GEN     " $@ && ./gen_service_table.py ksupport.elf > $@

services.c: service_table.h

main.o: main.c
	$(compile-dep)

%.o: %.c
	$(compile-dep)

%.o: %.S
	$(assemble)

libs:
	$(MAKE) -C $(MSCDIR)/software/libcompiler-rt
	$(MAKE) -C $(MSCDIR)/software/libbase
	$(MAKE) -C liblwip

clean:
	$(MAKE) -C liblwip clean
	$(RM) $(OBJECTS) $(OBJECTS:.o=.d) $(OBJECTS_KSUPPORT) $(OBJECTS_KSUPPORT:.o=.d)
	$(RM) runtime.elf runtime.bin runtime.fbi .*~ *~
	$(RM) service_table.h ksupport.elf ksupport.bin

.PHONY: all main.o clean libs load
