include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

CFLAGS += \
	-I$(LIBUNWIND_DIRECTORY) \
	-I$(LIBUNWIND_DIRECTORY)/../unwinder/include

LDFLAGS += \
	-L../libunwind

RUSTFLAGS += -Cpanic=unwind

all:: satman.bin satman.fbi

.PHONY: $(RUSTOUT)/libsatman.a
$(RUSTOUT)/libsatman.a:
	$(cargo) --target-dir ./cargo \
	--manifest-path $(SATMAN_DIRECTORY)/Cargo.toml \
	--target $(SATMAN_DIRECTORY)/../$(CARGO_TRIPLE).json

satman.elf: $(RUSTOUT)/libsatman.a ksupport_data.o
	$(link) -T $(SATMAN_DIRECTORY)/../firmware.ld \
	-lunwind-vexriscv-bare -m elf32lriscv

ksupport_data.o: ../ksupport/ksupport.elf 
	$(LD) -r -m elf32lriscv -b binary -o $@ $<

%.bin: %.elf
	$(objcopy) -O binary

%.fbi: %.bin
	$(mscimg) -f --little
