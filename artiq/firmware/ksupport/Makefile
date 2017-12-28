include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

CFLAGS += \
	-I$(LIBUNWIND_DIRECTORY) \
	-I$(LIBUNWIND_DIRECTORY)/../unwinder/include \
	-I$(MISOC_DIRECTORY)/software/include/dyld

LDFLAGS += --eh-frame-hdr \
	-L../libm \
	-L../libprintf \
	-L../libunwind

RUSTFLAGS += -Cpanic=unwind

all:: ksupport.elf

.PHONY: $(RUSTOUT)/libksupport.a
$(RUSTOUT)/libksupport.a:
	$(cargo) --manifest-path $(KSUPPORT_DIRECTORY)/Cargo.toml

ksupport.elf: $(RUSTOUT)/libksupport.a glue.o
	$(link) -T $(KSUPPORT_DIRECTORY)/ksupport.ld \
		-lunwind-elf -lprintf-float -lm

%.o: $(KSUPPORT_DIRECTORY)/%.c
	$(compile)
