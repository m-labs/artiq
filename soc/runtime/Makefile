include $(MSCDIR)/software/common.mak

OBJECTS_SERVICES=exception_jmp.o exceptions.o rtio.o dds.o
OBJECTS=isr.o elf_loader.o services.o comm_serial.o test_mode.o main.o

UNIPROCESSOR := $(shell echo -e "\#include <generated/csr.h>\nCSR_KERNEL_CPU_BASE" | $(CC_normal) $(CFLAGS) -E - | tail -n 1 | grep -c CSR_KERNEL_CPU_BASE)

ifeq ($(UNIPROCESSOR),0)
OBJECTS += kernelcpu.o ksupport_data.o
CFLAGS += -DARTIQ_BIPROCESSOR
SERVICE_TABLE_INPUT = ksupport.elf
else
ifeq ($(UNIPROCESSOR),1)
OBJECTS += $(OBJECTS_SERVICES)
else
$(error failed to determine uniprocessor/biprocessor build)
endif
endif

all: runtime.bin

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	@chmod -x $@

%.fbi: %.bin
	$(MSCDIR)/mkmscimg.py -f -o $@ $<

runtime.elf: $(OBJECTS) libs

%.elf:
	$(LD) $(LDFLAGS) \
		-T linker.ld \
		-N -o $@ \
		$(MSCDIR)/software/libbase/crt0-$(CPU).o \
		$(OBJECTS) \
		-L$(MSCDIR)/software/libbase \
		-L$(MSCDIR)/software/libcompiler-rt \
		-lbase -lcompiler-rt
	@chmod -x $@

ksupport.elf: $(OBJECTS_SERVICES) ksupport.o
	$(LD) $(LDFLAGS) \
		-T ksupport.ld \
		-N -o $@ \
		$(MSCDIR)/software/libbase/crt0-$(CPU).o \
		$^
	@chmod -x $@

ksupport_data.o: ksupport.bin
	$(LD) -r -b binary -o $@ $<

service_table.h: $(SERVICE_TABLE_INPUT)
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

clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.d) $(OBJECTS_SERVICES) $(OBJECTS_SERVICES:.o=.d)
	$(RM) runtime.elf runtime.bin runtime.fbi .*~ *~
	$(RM) service_table.h ksupport.d ksupport.o ksupport.elf ksupport.bin

.PHONY: all main.o clean libs load
