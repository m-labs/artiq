CC ?= clang

libartiq_personality.so: ../../soc/runtime/artiq_personality.c
	$(CC) -Wall -Werror -I. -fPIC -shared -o $@ $<
