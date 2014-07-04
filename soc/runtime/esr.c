#include <generated/csr.h>
#include <irq.h>
#include <uart.h>

static void isr(void)
{
	unsigned int irqs;
	
	irqs = irq_pending() & irq_getmask();
	
	if(irqs & (1 << UART_INTERRUPT))
		uart_isr();
}

#define EXTERNAL_IRQ 0x800
#define SYSTEM_CALL  0xc00

void exception_handler(unsigned long vect, unsigned long *sp);
void exception_handler(unsigned long vect, unsigned long *sp)
{
	vect &= 0xf00;
	if(vect == SYSTEM_CALL) {
		puts("scall");
	} else if(vect == EXTERNAL_IRQ) {
		isr();
	} else {
		/* Unhandled exception */
		for(;;);
	}
}
