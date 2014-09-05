#include <generated/csr.h>

#include "gpio.h"

void gpio_set(int channel, int value)
{
    static int csr_value;

    if(value)
        csr_value |= 1 << channel;
    else
        csr_value &= ~(1 << channel);
    leds_out_write(csr_value);
}
