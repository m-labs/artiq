#include <generated/csr.h>

#include "rtio.h"

void rtio_init(void)
{
    rtio_reset_write(1);
    rtio_reset_write(0);
    rtio_reset_phy_write(0);
}

long long int rtio_get_counter(void)
{
    rtio_counter_update_write(1);
    return rtio_counter_read();
}
