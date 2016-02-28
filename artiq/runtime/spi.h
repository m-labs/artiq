#ifndef __SPI_H
#define __SPI_H

#include <hw/common.h>
#include <generated/csr.h>
#include <generated/mem.h>

#define SPI_ADDR_DATA 0
#define SPI_ADDR_XFER 1
#define SPI_ADDR_CONFIG 2
#define SPI_WB_READ (1 << 2)

#define SPI_XFER_CS(x) (x)
#define SPI_XFER_WRITE_LENGTH(x) ((x) << 16)
#define SPI_XFER_READ_LENGTH(x) ((x) << 24)

void spi_write(long long int timestamp, int channel, int address, unsigned int data);
unsigned int spi_read(long long int timestamp, int channel, int address);

#endif /* __SPI_H */
