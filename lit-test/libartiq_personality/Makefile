CC ?= clang

libartiq_personality.so: ../../soc/runtime/artiq_personality.c artiq_terminate.c
	$(CC) -Wall -Werror -I. -I../../soc/runtime -fPIC -shared -o $@ $^
