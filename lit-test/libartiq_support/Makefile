CC ?= clang

libartiq_support.so: ../../artiq/runtime/artiq_personality.c artiq_terminate.c artiq_time.c
	$(CC) -std=c99 -Wall -Werror -I. -I../../artiq/runtime -g -fPIC -shared -o $@ $^
