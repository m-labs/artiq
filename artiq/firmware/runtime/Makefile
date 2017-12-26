include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

CFLAGS += \
	-I$(LIBUNWIND_DIRECTORY) \
	-I$(LIBUNWIND_DIRECTORY)/../unwinder/include \

LDFLAGS += -L../libbase \
	-L../libunwind

RUSTFLAGS += -Cpanic=abort

all: runtime.bin runtime.fbi

.PHONY: $(RUSTOUT)/libruntime.a
$(RUSTOUT)/libruntime.a:
	$(cargo) --manifest-path $(RUNTIME_DIRECTORY)/Cargo.toml

runtime.elf: $(RUSTOUT)/libruntime.a ksupport_data.o
	$(LD) $(LDFLAGS) -T $(RUNTIME_DIRECTORY)/runtime.ld -o $@ $^ \
		-lunwind-bare
	@chmod -x $@

ksupport_data.o: ../ksupport/ksupport.elf
	$(LD) -r -b binary -o $@ $<

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	@chmod -x $@

%.fbi: %.bin
	@echo " MSCIMG  " $@ && $(PYTHON) -m misoc.tools.mkmscimg -f -o $@ $<

clean:
	$(RM) *.o runtime.elf runtime.bin runtime.fbi
	$(RM) -rf cargo

.PHONY: all clean
