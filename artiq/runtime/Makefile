include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

PYTHON ?= python3.5

OBJECTS := flash_storage.o main.o
OBJECTS_KSUPPORT := ksupport_glue.o artiq_personality.o ad9154.o

RUSTOUT_DIRECTORY := cargo/or1k-unknown-none/debug
CORE_IO_COMMIT := d40c593f42fafbac1ff3d827f6df96338b5b7d8b
export CORE_IO_COMMIT

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

.PHONY: $(RUSTOUT_DIRECTORY)/libruntime.a
$(RUSTOUT_DIRECTORY)/libruntime.a: ksupport.elf
	CARGO_TARGET_DIR=$(realpath .)/cargo \
		cargo rustc --verbose \
			--manifest-path $(realpath $(RUNTIME_DIRECTORY)/../runtime.rs/Cargo.toml) \
			--target=or1k-unknown-none -- \
			$(shell cat $(BUILDINC_DIRECTORY)/generated/rust-cfg) \
			-C target-feature=+mul,+div,+ffl1,+cmov,+addc -C opt-level=s \
			-L../libcompiler-rt

runtime.elf: $(OBJECTS) $(RUSTOUT_DIRECTORY)/libruntime.a
	$(LD) $(LDFLAGS) \
		-T $(RUNTIME_DIRECTORY)/runtime.ld \
		-o $@ \
		$^ \
		-lbase-nofloat -lcompiler-rt -lalloc -llwip
	@chmod -x $@

.PHONY: $(RUSTOUT_DIRECTORY)/libksupport.a
$(RUSTOUT_DIRECTORY)/libksupport.a:
	CARGO_TARGET_DIR=$(realpath .)/cargo \
		cargo rustc --verbose \
			--manifest-path $(realpath $(RUNTIME_DIRECTORY)/../runtime.rs/libksupport/Cargo.toml) \
			--target=or1k-unknown-none -- \
			$(shell cat $(BUILDINC_DIRECTORY)/generated/rust-cfg) \
			--cfg ksupport \
			-C target-feature=+mul,+div,+ffl1,+cmov,+addc -C opt-level=s \
			-L../libcompiler-rt

ksupport.elf: $(OBJECTS_KSUPPORT) $(RUSTOUT_DIRECTORY)/libksupport.a
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

%.fbi: %.bin
	@echo " MSCIMG  " $@ && $(PYTHON) -m misoc.tools.mkmscimg -f -o $@ $<

clean:
	$(RM) $(OBJECTS) $(OBJECTS_KSUPPORT)
	$(RM) runtime.elf runtime.bin runtime.fbi .*~ *~
	$(RM) ksupport.elf ksupport.bin
	$(RM) -rf cargo

.PHONY: all clean
