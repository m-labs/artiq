include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

PYTHON ?= python3.5

OBJECTS := isr.o clock.o rtiocrg.o flash_storage.o mailbox.o \
	session.o log.o analyzer.o moninj.o net_server.o bridge_ctl.o \
	ksupport_data.o kloader.o test_mode.o main.o
OBJECTS_KSUPPORT := ksupport.o artiq_personality.o mailbox.o \
	bridge.o rtio.o ttl.o dds.o rt2wb.o

CFLAGS += -I$(LIBALLOC_DIRECTORY) \
	-I$(MISOC_DIRECTORY)/software/include/dyld \
	-I$(LIBDYLD_DIRECTORY)/include \
	-I$(LIBUNWIND_DIRECTORY) \
	-I$(LIBUNWIND_DIRECTORY)/../unwinder/include \
	-I$(LIBLWIP_DIRECTORY)/../lwip/src/include \
	-I$(LIBLWIP_DIRECTORY) \
	-DNDEBUG

all: runtime.bin runtime.fbi

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	@chmod -x $@

%.fbi: %.bin
	@echo " MSCIMG  " $@ && $(PYTHON) -m misoc.tools.mkmscimg -f -o $@ $<

runtime.elf: $(OBJECTS)
	$(LD) $(LDFLAGS) \
		-T $(RUNTIME_DIRECTORY)/runtime.ld \
		-N -o $@ \
		../libbase/crt0-$(CPU).o \
		$(OBJECTS) \
		-L../libcompiler_rt \
		-L../libbase \
		-L../libm \
		-L../liballoc \
		-L../liblwip \
		-lbase -lm -lcompiler_rt -lalloc -llwip
	@chmod -x $@

ksupport.elf: $(OBJECTS_KSUPPORT)
	$(LD) $(LDFLAGS) \
		--eh-frame-hdr \
		-T $(RUNTIME_DIRECTORY)/ksupport.ld \
		-N -o $@ \
		../libbase/crt0-$(CPU).o \
		$^ \
		-L../libbase \
		-L../libcompiler_rt \
		-L../libunwind \
		-L../libdyld \
		-lbase-nofloat -lcompiler_rt -ldyld -lunwind
	@chmod -x $@

ksupport_data.o: ksupport.elf
	$(LD) -r -b binary -o $@ $<

%.o: $(RUNTIME_DIRECTORY)/%.c
	$(compile)

%.o: $(RUNTIME_DIRECTORY)/%.S
	$(assemble)

clean:
	$(RM) $(OBJECTS) $(OBJECTS_KSUPPORT)
	$(RM) runtime.elf runtime.bin runtime.fbi .*~ *~
	$(RM) ksupport.elf ksupport.bin

.PHONY: all clean
