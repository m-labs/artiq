include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

RUSTFLAGS += -Cpanic=abort

export XBUILD_SYSROOT_PATH=$(BUILDINC_DIRECTORY)/../sysroot

all:: bootloader.bin

.PHONY: $(RUSTOUT)/libbootloader.a
$(RUSTOUT)/libbootloader.a:
	$(cargo) --target-dir ./cargo \
	--manifest-path $(BOOTLOADER_DIRECTORY)/Cargo.toml \
	--target $(BOOTLOADER_DIRECTORY)/../$(CARGO_TRIPLE).json

bootloader.elf: $(RUSTOUT)/libbootloader.a
	$(link) -T $(BOOTLOADER_DIRECTORY)/bootloader.ld

%.bin: %.elf
	$(objcopy) -O binary
	$(MSCIMG) $@ --little
