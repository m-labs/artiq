#include <stdio.h>
#include <string.h>
#include <irq.h>
#include <uart.h>
#include <console.h>
#include <system.h>
#include <time.h>
#include <generated/csr.h>

#include "test_mode.h"
#include "session.h"

void comm_service(void)
{
    char *txdata;
    int txlen;
    static char rxdata;
    static int rxpending;
    int r, i;

    if(!rxpending && uart_read_nonblock()) {
        rxdata = uart_read();
        rxpending = 1;
    }
    if(rxpending) {
        r = session_input(&rxdata, 1);
        if(r > 0)
            rxpending = 0;
    }

    session_poll((void **)&txdata, &txlen);
    if(txlen > 0) {
        for(i=0;i<txlen;i++)
            uart_write(txdata[i]);
        session_ack(txlen);
    }
}

static void regular_main(void)
{
    session_start();
    while(1)
        comm_service();
}


static void blink_led(void)
{
    int i, ev, p;

    p = identifier_frequency_read()/10;
    time_init();
    for(i=0;i<3;i++) {
        leds_out_write(1);
        while(!elapsed(&ev, p));
        leds_out_write(0);
        while(!elapsed(&ev, p));
    }
}

static int check_test_mode(void)
{
    char c;

    timer0_en_write(0);
    timer0_reload_write(0);
    timer0_load_write(identifier_frequency_read() >> 2);
    timer0_en_write(1);
    timer0_update_value_write(1);
    while(timer0_value_read()) {
        if(readchar_nonblock()) {
            c = readchar();
            if((c == 't')||(c == 'T'))
                return 1;
        }
        timer0_update_value_write(1);
    }
    return 0;
}

int main(void)
{
    irq_setmask(0);
    irq_setie(1);
    uart_init();

#ifdef ARTIQ_AMP
    puts("ARTIQ runtime built "__DATE__" "__TIME__" for AMP systems\n");
#else
    puts("ARTIQ runtime built "__DATE__" "__TIME__" for UP systems\n");
#endif
    blink_led();

    if(check_test_mode()) {
        puts("Entering test mode.");
        test_main();
    } else {
        puts("Entering regular mode.");
        regular_main();
    }
    return 0;
}
