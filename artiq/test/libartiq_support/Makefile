CC ?= clang

libartiq_support.so: ../../firmware/ksupport/artiq_personality.c artiq_terminate.c artiq_time.c
	$(CC) -std=c99 -Wall -Werror -I. -I../../firmware/ksupport -g -fPIC -shared -o $@ $^
