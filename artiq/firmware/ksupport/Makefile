include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

CFLAGS += \
	-I$(LIBUNWIND_DIRECTORY) \
	-I$(LIBUNWIND_DIRECTORY)/../unwinder/include \
	-I$(MISOC_DIRECTORY)/software/include/dyld

LDFLAGS += --eh-frame-hdr \
	--nmagic \
	-L../libm \
	-L../libprintf \
	-L../libunwind

RUSTFLAGS += -Cpanic=unwind

export XBUILD_SYSROOT_PATH=$(BUILDINC_DIRECTORY)/../sysroot

all:: ksupport.elf

.PHONY: $(RUSTOUT)/libksupport.a
$(RUSTOUT)/libksupport.a:
	$(cargo) --target-dir ./cargo \
	--manifest-path $(KSUPPORT_DIRECTORY)/Cargo.toml \
	--target $(KSUPPORT_DIRECTORY)/../$(CARGO_TRIPLE).json

ksupport.elf: $(RUSTOUT)/libksupport.a glue.o
	$(link) -T $(KSUPPORT_DIRECTORY)/ksupport.ld \
		-lunwind-$(CPU)-elf -lprintf-float -lm

%.o: $(KSUPPORT_DIRECTORY)/%.c
	$(compile)
