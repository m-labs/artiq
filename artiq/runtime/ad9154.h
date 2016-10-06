#ifndef __AD9154_H
#define __AD9154_H

#ifdef CONFIG_AD9154_DAC_CS

void ad9154_init(void);
void ad9154_write(uint16_t addr, uint8_t data);
uint8_t ad9154_read(uint16_t addr);

void ad9516_write(uint16_t addr, uint8_t data);
uint8_t ad9516_read(uint16_t addr);

void ad9154_jesd_enable(int en);
int ad9154_jesd_ready(void);
void ad9154_jesd_prbs(int p);

#endif
#endif
