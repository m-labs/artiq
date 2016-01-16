#ifndef __BRIDGE_CTL_H
#define __BRIDGE_CTL_H

void brg_start(void);

void brg_ttloe(int n, int value);
void brg_ttlo(int n, int value);

void brg_ddssel(int channel);
void brg_ddsreset(void);
unsigned int brg_ddsread(unsigned int address);
void brg_ddswrite(unsigned int address, unsigned int data);
void brg_ddsfud(void);

#endif /* __BRIDGE_CTL_H */
