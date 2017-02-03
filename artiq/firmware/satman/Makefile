include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

PYTHON ?= python3

RUSTOUT := cargo/or1k-unknown-none/debug

LDFLAGS += --gc-sections \
	-L../libbase

RUSTFLAGS = \
	-C target-feature=+mul,+div,+ffl1,+cmov,+addc \
	-C opt-level=s \
	-C panic=abort
export RUSTFLAGS

all: satman.bin satman.fbi

.PHONY: $(RUSTOUT)/libsatman.a
$(RUSTOUT)/libsatman.a:
	CARGO_TARGET_DIR=$(realpath .)/cargo \
		cargo build --target=or1k-unknown-none \
			--manifest-path $(realpath $(SATMAN_DIRECTORY))/Cargo.toml

satman.elf: $(RUSTOUT)/libsatman.a
	$(LD) $(LDFLAGS) -T $(SATMAN_DIRECTORY)/satman.ld -o $@ $^
	@chmod -x $@

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	@chmod -x $@

%.fbi: %.bin
	@echo " MSCIMG  " $@ && $(PYTHON) -m misoc.tools.mkmscimg -f -o $@ $<

clean:
	$(RM) satman.elf satman.bin satman.fbi .*~ *~
	$(RM) -rf cargo

.PHONY: all clean
