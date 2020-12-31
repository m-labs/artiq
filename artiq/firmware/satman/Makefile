include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

LDFLAGS += -L../libbase

RUSTFLAGS += -Cpanic=abort

all:: satman.bin satman.fbi

.PHONY: $(RUSTOUT)/libsatman.a
$(RUSTOUT)/libsatman.a:
	$(cargo) --manifest-path $(SATMAN_DIRECTORY)/Cargo.toml

satman.elf: $(RUSTOUT)/libsatman.a
	$(link) -T $(SATMAN_DIRECTORY)/satman.ld

%.bin: %.elf
	$(objcopy) -O binary

%.fbi: %.bin
	$(mscimg) -f
