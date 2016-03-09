#ifndef __BRIDGE_CTL_H
#define __BRIDGE_CTL_H

void brg_start(void);

void brg_ttloe(int n, int value);
void brg_ttlo(int n, int value);

void brg_ddssel(int bus_channel, int channel);
void brg_ddsreset(int bus_channel);
unsigned int brg_ddsread(int bus_channel, unsigned int address);
void brg_ddswrite(int bus_channel, unsigned int address, unsigned int data);
void brg_ddsfud(int bus_channel);

#endif /* __BRIDGE_CTL_H */
