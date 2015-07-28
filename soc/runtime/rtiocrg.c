#include <stdio.h>
#include <generated/csr.h>

#include "clock.h"
#include "flash_storage.h"
#include "rtiocrg.h"

void rtiocrg_init(void)
{
    char b;
    int clk;

#ifdef CSR_RTIO_CRG_PLL_RESET_ADDR
    rtio_crg_pll_reset_write(0);
#endif
    b = 'i';
    clk = 0;
    fs_read("startup_clock", &b, 1, NULL);
    if(b == 'i')
        printf("Startup RTIO clock: internal\n");
    else if(b == 'e') {
        printf("Startup RTIO clock: external\n");
        clk = 1;
    } else
        printf("WARNING: unknown startup_clock entry in flash storage\n");

    if(!rtiocrg_switch_clock(clk)) {
        printf("WARNING: startup RTIO clock failed\n");
        printf("WARNING: this may cause the system initialization to fail\n");
        printf("WARNING: fix clocking and reset the device\n");
    }
}

int rtiocrg_check(void)
{
#ifdef CSR_RTIO_CRG_PLL_RESET_ADDR
    return rtio_crg_pll_locked_read();
#else
    return 1;
#endif
}

int rtiocrg_switch_clock(int clk)
{
    int current_clk;

    current_clk = rtio_crg_clock_sel_read();
    if(clk == current_clk) {
#ifdef CSR_RTIO_CRG_PLL_RESET_ADDR
        busywait_us(150);
        if(!rtio_crg_pll_locked_read())
            return 0;
#endif
        return 1;
    }
#ifdef CSR_RTIO_CRG_PLL_RESET_ADDR
    rtio_crg_pll_reset_write(1);
#endif
    rtio_crg_clock_sel_write(clk);
#ifdef CSR_RTIO_CRG_PLL_RESET_ADDR
    rtio_crg_pll_reset_write(0);
    busywait_us(150);
    if(!rtio_crg_pll_locked_read())
        return 0;
#endif
    return 1;
}
