#include <hw/common.h>

#include "dds.h"

#define DDS_FTW0  0x0a
#define DDS_FTW1  0x0b
#define DDS_FTW2  0x0c
#define DDS_FTW3  0x0d
#define DDS_FUD   0x40
#define DDS_GPIO  0x41

#define DDS_READ(addr) \
	MMPTR(0xb0000000 + (addr)*4)

#define DDS_WRITE(addr, data) \
	MMPTR(0xb0000000 + (addr)*4) = data

void dds_init(void)
{
	int i;

	DDS_WRITE(DDS_GPIO, 1 << 7);

	for(i=0;i<8;i++) {
		DDS_WRITE(DDS_GPIO, i);
		DDS_WRITE(0x00, 0x78);
		DDS_WRITE(0x01, 0x00);
		DDS_WRITE(0x02, 0x00);
		DDS_WRITE(0x03, 0x00);
		DDS_WRITE(DDS_FUD, 0);
	}
}

void dds_program(int channel, int ftw)
{
	DDS_WRITE(DDS_GPIO, channel);
	DDS_WRITE(DDS_FTW0, ftw & 0xff);
	DDS_WRITE(DDS_FTW1, (ftw >> 8) & 0xff);
	DDS_WRITE(DDS_FTW2, (ftw >> 16) & 0xff);
	DDS_WRITE(DDS_FTW3, (ftw >> 24) & 0xff);
	DDS_WRITE(DDS_FUD, 0);
}
