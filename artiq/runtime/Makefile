include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

PYTHON ?= python3.5

OBJECTS := isr.o clock.o rtiocrg.o flash_storage.o mailbox.o \
	session.o log.o analyzer.o moninj.o net_server.o \
	ksupport_data.o kloader.o main.o
OBJECTS_KSUPPORT := ksupport.o artiq_personality.o mailbox.o \
	rtio.o dds.o i2c.o

CFLAGS += -I$(LIBALLOC_DIRECTORY) \
	-I$(MISOC_DIRECTORY)/software/include/dyld \
	-I$(LIBDYLD_DIRECTORY)/include \
	-I$(LIBUNWIND_DIRECTORY) \
	-I$(LIBUNWIND_DIRECTORY)/../unwinder/include \
	-I$(LIBLWIP_DIRECTORY)/../lwip/src/include \
	-I$(LIBLWIP_DIRECTORY) \
	-DNDEBUG

all: runtime.bin runtime.fbi

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	@chmod -x $@

%.fbi: %.bin
	@echo " MSCIMG  " $@ && $(PYTHON) -m misoc.tools.mkmscimg -f -o $@ $<

runtime.elf: $(OBJECTS) libruntime.a
	$(LD) $(LDFLAGS) \
		--gc-sections \
		-T $(RUNTIME_DIRECTORY)/runtime.ld \
		-N -o $@ \
		../libbase/crt0-$(CPU).o \
		$(OBJECTS) \
		-L../libcompiler-rt \
		-L../libbase \
		-L../liballoc \
		-L../liblwip \
		-Lcargo/or1k-unknown-none/debug/ \
		-lruntime -lbase-nofloat -lcompiler-rt -lalloc -llwip
	@chmod -x $@

ksupport.elf: $(OBJECTS_KSUPPORT)
	$(LD) $(LDFLAGS) \
		--eh-frame-hdr \
		-T $(RUNTIME_DIRECTORY)/ksupport.ld \
		-N -o $@ \
		../libbase/crt0-$(CPU).o \
		$^ \
		-L../libbase \
		-L../libm \
		-L../libcompiler-rt \
		-L../libunwind \
		-L../libdyld \
		-lbase -lm -lcompiler-rt -ldyld -lunwind
	@chmod -x $@

ksupport_data.o: ksupport.elf
	$(LD) -r -b binary -o $@ $<

libruntime.a:
	CARGO_TARGET_DIR="./cargo" \
		cargo rustc --verbose \
			--manifest-path $(RUNTIME_DIRECTORY)/../runtime.rs/Cargo.toml \
			--target=or1k-unknown-none -- \
			-C target-feature=+mul,+div,+ffl1,+cmov,+addc -C opt-level=s \
			-L../libcompiler-rt

%.o: $(RUNTIME_DIRECTORY)/%.c
	$(compile)

%.o: $(RUNTIME_DIRECTORY)/%.S
	$(assemble)

clean:
	$(RM) $(OBJECTS) $(OBJECTS_KSUPPORT)
	$(RM) runtime.elf runtime.bin runtime.fbi .*~ *~
	$(RM) ksupport.elf ksupport.bin

.PHONY: all clean
