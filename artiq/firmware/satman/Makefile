include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

LDFLAGS += -L../libbase

RUSTFLAGS += -Cpanic=abort

all: satman.bin satman.fbi

.PHONY: $(RUSTOUT)/libsatman.a
$(RUSTOUT)/libsatman.a:
	$(cargo) --manifest-path $(SATMAN_DIRECTORY)/Cargo.toml

satman.elf: $(RUSTOUT)/libsatman.a
	$(LD) $(LDFLAGS) -T $(SATMAN_DIRECTORY)/satman.ld -o $@ $^
	@chmod -x $@

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	@chmod -x $@

%.fbi: %.bin
	@echo " MSCIMG  " $@ && $(PYTHON) -m misoc.tools.mkmscimg -f -o $@ $<

clean:
	$(RM) satman.elf satman.bin satman.fbi
	$(RM) -rf cargo

.PHONY: all clean
