include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

PYTHON ?= python3.5

OBJECTS := main.o

RUSTOUT := cargo/or1k-unknown-none/debug

LDFLAGS += --gc-sections \
	-L../libcompiler-rt \
	-L../libbase \
	-L../liballoc

all: satman.bin satman.fbi

.PHONY: $(RUSTOUT)/libsatman.a
$(RUSTOUT)/libsatman.a:
	RUSTFLAGS="-C target-feature=+mul,+div,+ffl1,+cmov,+addc -C opt-level=s -Cpanic=abort" \
	CARGO_TARGET_DIR=$(realpath .)/cargo \
		cargo build --target=or1k-unknown-none \
			--manifest-path $(realpath $(SATMAN_DIRECTORY))/Cargo.toml

satman.elf: $(OBJECTS) $(RUSTOUT)/libsatman.a
	$(LD) $(LDFLAGS) \
		-T $(SATMAN_DIRECTORY)/satman.ld \
		-o $@ \
		$^ \
		-lbase-nofloat -lcompiler-rt -lalloc
	@chmod -x $@

%.o: $(SATMAN_DIRECTORY)/%.c
	$(compile)

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	@chmod -x $@

%.fbi: %.bin
	@echo " MSCIMG  " $@ && $(PYTHON) -m misoc.tools.mkmscimg -f -o $@ $<

clean:
	$(RM) $(OBJECTS)
	$(RM) satman.elf satman.bin satman.fbi .*~ *~
	$(RM) -rf cargo

.PHONY: all clean
