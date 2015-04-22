include $(MSCDIR)/software/common.mak

OBJECTS := isr.o elf_loader.o services.o session.o log.o test_mode.o kloader.o main.o
OBJECTS_KSUPPORT := exception_jmp.o exceptions.o rtio.o dds.o

# NOTE: this does not handle dependencies well. Run "make clean"
# when switching between UP and AMP.
UNIPROCESSOR := $(shell printf "\#include <generated/csr.h>\nCSR_KERNEL_CPU_BASE" | $(CC_normal) $(CFLAGS) -E - | tail -n 1 | grep -c CSR_KERNEL_CPU_BASE)

ifeq ($(UNIPROCESSOR),0)
OBJECTS += mailbox.o ksupport_data.o
OBJECTS_KSUPPORT += mailbox.o bridge.o ksupport.o
CFLAGS += -DARTIQ_AMP
SERVICE_TABLE_INPUT = ksupport.elf
else
ifeq ($(UNIPROCESSOR),1)
OBJECTS += $(OBJECTS_KSUPPORT)
else
$(error failed to determine UP/AMP build)
endif
endif

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
		$^
	@chmod -x $@

ksupport_data.o: ksupport.bin
	$(LD) -r -b binary -o $@ $<

service_table.h: $(SERVICE_TABLE_INPUT) gen_service_table.py
	@echo " GEN     " $@ && ./gen_service_table.py $(SERVICE_TABLE_INPUT) > $@

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
