include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

CFLAGS += \
	-I$(LIBUNWIND_DIRECTORY) \
	-I$(LIBUNWIND_DIRECTORY)/../unwinder/include \
	-I$(MISOC_DIRECTORY)/software/include/dyld
CFLAGS += -DNDEBUG

LDFLAGS += --eh-frame-hdr \
	-L../libcompiler-rt \
	-L../libbase \
	-L../libm \
	-L../libunwind

RUSTFLAGS += -Cpanic=unwind

all: ksupport.elf

.PHONY: $(RUSTOUT)/libksupport.a
$(RUSTOUT)/libksupport.a:
	$(cargo) --manifest-path $(KSUPPORT_DIRECTORY)/Cargo.toml

ksupport.elf: $(RUSTOUT)/libksupport.a glue.o
	$(LD) $(LDFLAGS) -T $(KSUPPORT_DIRECTORY)/ksupport.ld -o $@ $^ \
		-lunwind -lcompiler-rt -lbase -lm
	@chmod -x $@

%.o: $(KSUPPORT_DIRECTORY)/%.c
	$(compile)

clean:
	$(RM) *.o ksupport.elf
	$(RM) -rf cargo

.PHONY: all clean
