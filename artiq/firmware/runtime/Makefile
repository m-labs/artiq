include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

CFLAGS += \
	-I$(LIBUNWIND_DIRECTORY) \
	-I$(LIBUNWIND_DIRECTORY)/../unwinder/include

LDFLAGS += \
	-L../libunwind

RUSTFLAGS += -Cpanic=unwind

all:: runtime.bin runtime.fbi

.PHONY: $(RUSTOUT)/libruntime.a
$(RUSTOUT)/libruntime.a:
	$(cargo) --manifest-path $(RUNTIME_DIRECTORY)/Cargo.toml

runtime.elf: $(RUSTOUT)/libruntime.a ksupport_data.o
	$(link) -T $(RUNTIME_DIRECTORY)/runtime.ld \
		-lunwind-bare

ksupport_data.o: ../ksupport/ksupport.elf
	$(LD) -r -b binary -o $@ $<

%.bin: %.elf
	$(objcopy) -O binary

%.fbi: %.bin
	$(mscimg) -f
