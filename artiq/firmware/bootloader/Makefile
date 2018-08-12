include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

RUSTFLAGS += -Cpanic=abort

all:: bootloader.bin

.PHONY: $(RUSTOUT)/libbootloader.a
$(RUSTOUT)/libbootloader.a:
	$(cargo) --manifest-path $(BOOTLOADER_DIRECTORY)/Cargo.toml

bootloader.elf: $(RUSTOUT)/libbootloader.a
	$(link) -T $(BOOTLOADER_DIRECTORY)/bootloader.ld

%.bin: %.elf
	$(objcopy) -O binary
	$(MSCIMG) $@
