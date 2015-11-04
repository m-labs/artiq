include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

PYTHON ?= python3

OBJECTS := isr.o flash_storage.o clock.o rtiocrg.o elf_loader.o services.o session.o log.o test_mode.o kloader.o bridge_ctl.o mailbox.o ksupport_data.o net_server.o moninj.o main.o
OBJECTS_KSUPPORT := ksupport.o exception_jmp.o exceptions.o mailbox.o bridge.o rtio.o ttl.o dds.o

CFLAGS += -I$(LIBLWIP_DIRECTORY)/../lwip/src/include -I$(LIBLWIP_DIRECTORY) -I.

all: runtime.bin runtime.fbi

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	@chmod -x $@

%.fbi: %.bin
	@echo " MSCIMG  " $@ && $(PYTHON) -m misoc.tools.mkmscimg -f -o $@ $<

runtime.elf: $(OBJECTS)
	$(LD) $(LDFLAGS) \
		-T $(RUNTIME_DIRECTORY)/linker.ld \
		-N -o $@ \
		../libbase/crt0-$(CPU).o \
		$(OBJECTS) \
		-L../libbase \
		-L../libcompiler_rt \
		-L../liblwip \
		-lbase -lcompiler_rt -llwip
	@chmod -x $@

ksupport.elf: $(OBJECTS_KSUPPORT)
	$(LD) $(LDFLAGS) \
		-T $(RUNTIME_DIRECTORY)/ksupport.ld \
		-N -o $@ \
		../libbase/crt0-$(CPU).o \
		$^ \
		-L../libcompiler_rt \
		-lcompiler_rt
	@chmod -x $@

ksupport_data.o: ksupport.bin
	$(LD) -r -b binary -o $@ $<

service_table.h: ksupport.elf $(RUNTIME_DIRECTORY)/gen_service_table.py
	@echo " GEN     " $@ && $(PYTHON) $(RUNTIME_DIRECTORY)/gen_service_table.py ksupport.elf > $@

$(RUNTIME_DIRECTORY)/services.c: service_table.h

services.o: $(RUNTIME_DIRECTORY)/services.c service_table.h
	$(compile)

main.o: $(RUNTIME_DIRECTORY)/main.c
	$(compile)

%.o: $(RUNTIME_DIRECTORY)/%.c
	$(compile)

%.o: $(RUNTIME_DIRECTORY)/%.S
	$(assemble)

clean:
	$(RM) $(OBJECTS) $(OBJECTS_KSUPPORT)
	$(RM) runtime.elf runtime.bin runtime.fbi .*~ *~
	$(RM) service_table.h ksupport.elf ksupport.bin

.PHONY: all clean main.o
