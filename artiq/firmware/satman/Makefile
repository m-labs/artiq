include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

LDFLAGS += -L../libbase

RUSTFLAGS += -Cpanic=abort

export XBUILD_SYSROOT_PATH=$(BUILDINC_DIRECTORY)/../sysroot

all:: satman.bin satman.fbi

.PHONY: $(RUSTOUT)/libsatman.a
$(RUSTOUT)/libsatman.a:
	$(cargo) --target-dir ./cargo \
	--manifest-path $(SATMAN_DIRECTORY)/Cargo.toml \
	--target $(SATMAN_DIRECTORY)/../$(CARGO_TRIPLE).json

satman.elf: $(RUSTOUT)/libsatman.a
	$(link) -T $(SATMAN_DIRECTORY)/satman.ld

%.bin: %.elf
	$(objcopy) -O binary

%.fbi: %.bin
	$(mscimg) -f --little
