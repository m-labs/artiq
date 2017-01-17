include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

PYTHON ?= python3.5

RUSTOUT := cargo/or1k-unknown-none/debug
RUSTOUT_KSUPPORT := cargo-ksupport/or1k-unknown-none/debug

CFLAGS += \
	-I$(LIBALLOC_DIRECTORY) \
	-I$(MISOC_DIRECTORY)/software/include/dyld \
	-I$(LIBDYLD_DIRECTORY)/include \
	-I$(LIBUNWIND_DIRECTORY) \
	-I$(LIBUNWIND_DIRECTORY)/../unwinder/include \
	-I$(LIBLWIP_DIRECTORY)/../lwip/src/include \
	-I$(LIBLWIP_DIRECTORY)
CFLAGS += -DNDEBUG

LDFLAGS += --gc-sections \
	-L../libcompiler-rt \
	-L../libbase \
	-L../libm \
	-L../liballoc \
	-L../libunwind \
	-L../libdyld \
	-L../liblwip

all: runtime.bin runtime.fbi

.PHONY: $(RUSTOUT)/libruntime.a
$(RUSTOUT)/libruntime.a:
	RUSTFLAGS="-C target-feature=+mul,+div,+ffl1,+cmov,+addc -C opt-level=s -Cpanic=abort" \
	CARGO_TARGET_DIR=$(realpath .)/cargo \
		cargo build --target=or1k-unknown-none \
			--manifest-path $(realpath $(RUNTIME_DIRECTORY)/../firmware/runtime/Cargo.toml)

runtime.elf: $(RUSTOUT)/libruntime.a flash_storage.o main.o ksupport_data.o
	$(LD) $(LDFLAGS) \
		-T $(RUNTIME_DIRECTORY)/runtime.ld \
		-o $@ \
		$^ \
		-lbase-nofloat -lcompiler-rt -lalloc -llwip
	@chmod -x $@

.PHONY: $(RUSTOUT_KSUPPORT)/libksupport.a
$(RUSTOUT_KSUPPORT)/libksupport.a:
	RUSTFLAGS="-C target-feature=+mul,+div,+ffl1,+cmov,+addc -C opt-level=s -Cpanic=unwind" \
	CARGO_TARGET_DIR=$(realpath .)/cargo-ksupport \
		cargo build --target=or1k-unknown-none \
			--manifest-path $(realpath $(RUNTIME_DIRECTORY)/../firmware/libksupport/Cargo.toml)

ksupport.elf: $(RUSTOUT_KSUPPORT)/libksupport.a ksupport_glue.o artiq_personality.o
	$(LD) $(LDFLAGS) \
		--eh-frame-hdr \
		-T $(RUNTIME_DIRECTORY)/ksupport.ld \
		-o $@ \
		$^ \
		-lbase -lm -lcompiler-rt -ldyld -lunwind
	@chmod -x $@

%.o: $(RUNTIME_DIRECTORY)/%.c
	$(compile)

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	@chmod -x $@

%_data.o: %.elf
	$(LD) -r -b binary -o $@ $<

%.fbi: %.bin
	@echo " MSCIMG  " $@ && $(PYTHON) -m misoc.tools.mkmscimg -f -o $@ $<

clean:
	$(RM) $(OBJECTS) $(OBJECTS_KSUPPORT)
	$(RM) runtime.elf runtime.bin runtime.fbi .*~ *~
	$(RM) ksupport.elf ksupport.bin
	$(RM) -rf cargo

.PHONY: all clean
