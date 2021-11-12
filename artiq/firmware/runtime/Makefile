include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

CFLAGS += \
	-I$(LIBUNWIND_DIRECTORY) \
	-I$(LIBUNWIND_DIRECTORY)/../unwinder/include

LDFLAGS += \
	-L../libunwind

RUSTFLAGS += -Cpanic=unwind

export XBUILD_SYSROOT_PATH=$(BUILDINC_DIRECTORY)/../sysroot

all:: runtime.bin runtime.fbi

.PHONY: $(RUSTOUT)/libruntime.a
$(RUSTOUT)/libruntime.a:
	$(cargo) --target-dir ./cargo \
	--manifest-path $(RUNTIME_DIRECTORY)/Cargo.toml \
	--target $(RUNTIME_DIRECTORY)/../$(CARGO_TRIPLE).json

runtime.elf: $(RUSTOUT)/libruntime.a ksupport_data.o
	$(link) -T $(RUNTIME_DIRECTORY)/runtime.ld \
		-lunwind-bare -m elf32lriscv

ksupport_data.o: ../ksupport/ksupport.elf
	$(LD) -r -m elf32lriscv -b binary -o $@ $<

%.bin: %.elf
	$(objcopy) -O binary

%.fbi: %.bin
	$(mscimg) -f --little
