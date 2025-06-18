#ifndef __GENERATED_CSR_H
#define __GENERATED_CSR_H
#include <hw/common.h>

/* rtio */
#define CSR_RTIO_BASE 0xa0000000
#define CSR_RTIO_TARGET_ADDR 0xa0000000
#define CSR_RTIO_TARGET_SIZE 1
static inline unsigned int rtio_target_read(void) {
	unsigned int r = MMPTR(0xa0000000);
	return r;
}
static inline void rtio_target_write(unsigned int value) {
	MMPTR(0xa0000000) = value;
}
#define CSR_RTIO_NOW_HI_ADDR 0xa0000008
#define CSR_RTIO_NOW_HI_SIZE 1
static inline unsigned int rtio_now_hi_read(void) {
	unsigned int r = MMPTR(0xa0000008);
	return r;
}
static inline void rtio_now_hi_write(unsigned int value) {
	MMPTR(0xa0000008) = value;
}
#define CSR_RTIO_NOW_LO_ADDR 0xa0000010
#define CSR_RTIO_NOW_LO_SIZE 1
static inline unsigned int rtio_now_lo_read(void) {
	unsigned int r = MMPTR(0xa0000010);
	return r;
}
static inline void rtio_now_lo_write(unsigned int value) {
	MMPTR(0xa0000010) = value;
}
#define CSR_RTIO_O_DATA_ADDR 0xa0000018
#define CSR_RTIO_O_DATA_SIZE 16
#define CSR_RTIO_O_STATUS_ADDR 0xa0000098
#define CSR_RTIO_O_STATUS_SIZE 1
static inline unsigned int rtio_o_status_read(void) {
	unsigned int r = MMPTR(0xa0000098);
	return r;
}
#define CSR_RTIO_I_TIMEOUT_ADDR 0xa00000a0
#define CSR_RTIO_I_TIMEOUT_SIZE 2
static inline unsigned long long int rtio_i_timeout_read(void) {
	unsigned long long int r = MMPTR(0xa00000a0);
	r <<= 32;
	r |= MMPTR(0xa00000a8);
	return r;
}
static inline void rtio_i_timeout_write(unsigned long long int value) {
	MMPTR(0xa00000a0) = value >> 32;
	MMPTR(0xa00000a8) = value;
}
#define CSR_RTIO_I_DATA_ADDR 0xa00000b0
#define CSR_RTIO_I_DATA_SIZE 1
static inline unsigned int rtio_i_data_read(void) {
	unsigned int r = MMPTR(0xa00000b0);
	return r;
}
#define CSR_RTIO_I_TIMESTAMP_ADDR 0xa00000b8
#define CSR_RTIO_I_TIMESTAMP_SIZE 2
static inline unsigned long long int rtio_i_timestamp_read(void) {
	unsigned long long int r = MMPTR(0xa00000b8);
	r <<= 32;
	r |= MMPTR(0xa00000c0);
	return r;
}
#define CSR_RTIO_I_STATUS_ADDR 0xa00000c8
#define CSR_RTIO_I_STATUS_SIZE 1
static inline unsigned int rtio_i_status_read(void) {
	unsigned int r = MMPTR(0xa00000c8);
	return r;
}
#define CSR_RTIO_COUNTER_ADDR 0xa00000d0
#define CSR_RTIO_COUNTER_SIZE 2
static inline unsigned long long int rtio_counter_read(void) {
	unsigned long long int r = MMPTR(0xa00000d0);
	r <<= 32;
	r |= MMPTR(0xa00000d8);
	return r;
}
#define CSR_RTIO_COUNTER_UPDATE_ADDR 0xa00000e0
#define CSR_RTIO_COUNTER_UPDATE_SIZE 1
static inline unsigned int rtio_counter_update_read(void) {
	unsigned int r = MMPTR(0xa00000e0);
	return r;
}
static inline void rtio_counter_update_write(unsigned int value) {
	MMPTR(0xa00000e0) = value;
}

/* rtio_dma */
#define CSR_RTIO_DMA_BASE 0xb0000000
#define CSR_RTIO_DMA_ENABLE_ADDR 0xb0000000
#define CSR_RTIO_DMA_ENABLE_SIZE 1
static inline unsigned int rtio_dma_enable_read(void) {
	unsigned int r = MMPTR(0xb0000000);
	return r;
}
static inline void rtio_dma_enable_write(unsigned int value) {
	MMPTR(0xb0000000) = value;
}
#define CSR_RTIO_DMA_BASE_ADDRESS_ADDR 0xb0000008
#define CSR_RTIO_DMA_BASE_ADDRESS_SIZE 2
static inline unsigned long long int rtio_dma_base_address_read(void) {
	unsigned long long int r = MMPTR(0xb0000008);
	r <<= 32;
	r |= MMPTR(0xb0000010);
	return r;
}
static inline void rtio_dma_base_address_write(unsigned long long int value) {
	MMPTR(0xb0000008) = value >> 32;
	MMPTR(0xb0000010) = value;
}
#define CSR_RTIO_DMA_TIME_OFFSET_ADDR 0xb0000018
#define CSR_RTIO_DMA_TIME_OFFSET_SIZE 2
static inline unsigned long long int rtio_dma_time_offset_read(void) {
	unsigned long long int r = MMPTR(0xb0000018);
	r <<= 32;
	r |= MMPTR(0xb0000020);
	return r;
}
static inline void rtio_dma_time_offset_write(unsigned long long int value) {
	MMPTR(0xb0000018) = value >> 32;
	MMPTR(0xb0000020) = value;
}
#define CSR_RTIO_DMA_ERROR_ADDR 0xb0000028
#define CSR_RTIO_DMA_ERROR_SIZE 1
static inline unsigned int rtio_dma_error_read(void) {
	unsigned int r = MMPTR(0xb0000028);
	return r;
}
static inline void rtio_dma_error_write(unsigned int value) {
	MMPTR(0xb0000028) = value;
}
#define CSR_RTIO_DMA_ERROR_CHANNEL_ADDR 0xb0000030
#define CSR_RTIO_DMA_ERROR_CHANNEL_SIZE 1
static inline unsigned int rtio_dma_error_channel_read(void) {
	unsigned int r = MMPTR(0xb0000030);
	return r;
}
#define CSR_RTIO_DMA_ERROR_TIMESTAMP_ADDR 0xb0000038
#define CSR_RTIO_DMA_ERROR_TIMESTAMP_SIZE 2
static inline unsigned long long int rtio_dma_error_timestamp_read(void) {
	unsigned long long int r = MMPTR(0xb0000038);
	r <<= 32;
	r |= MMPTR(0xb0000040);
	return r;
}
#define CSR_RTIO_DMA_ERROR_ADDRESS_ADDR 0xb0000048
#define CSR_RTIO_DMA_ERROR_ADDRESS_SIZE 1
static inline unsigned int rtio_dma_error_address_read(void) {
	unsigned int r = MMPTR(0xb0000048);
	return r;
}

/* cri_con */
#define CSR_CRI_CON_BASE 0x90000000
#define CSR_CRI_CON_SELECTED_ADDR 0x90000000
#define CSR_CRI_CON_SELECTED_SIZE 1
static inline unsigned int cri_con_selected_read(void) {
	unsigned int r = MMPTR(0x90000000);
	return r;
}
static inline void cri_con_selected_write(unsigned int value) {
	MMPTR(0x90000000) = value;
}

/* crg */
#define CSR_CRG_BASE 0xe0003000
#define CSR_CRG_SWITCH_DONE_ADDR 0xe0003000
#define CSR_CRG_SWITCH_DONE_SIZE 1
static inline unsigned char crg_switch_done_read(void) {
	unsigned char r = MMPTR(0xe0003000);
	return r;
}
#define CSR_CRG_CLOCK_SEL_ADDR 0xe0003008
#define CSR_CRG_CLOCK_SEL_SIZE 1
static inline unsigned char crg_clock_sel_read(void) {
	unsigned char r = MMPTR(0xe0003008);
	return r;
}
static inline void crg_clock_sel_write(unsigned char value) {
	MMPTR(0xe0003008) = value;
}

/* ddrphy */
#define CSR_DDRPHY_BASE 0xe0003800
#define CSR_DDRPHY_DLY_SEL_ADDR 0xe0003800
#define CSR_DDRPHY_DLY_SEL_SIZE 1
static inline unsigned char ddrphy_dly_sel_read(void) {
	unsigned char r = MMPTR(0xe0003800);
	return r;
}
static inline void ddrphy_dly_sel_write(unsigned char value) {
	MMPTR(0xe0003800) = value;
}
#define CSR_DDRPHY_RDLY_DQ_RST_ADDR 0xe0003808
#define CSR_DDRPHY_RDLY_DQ_RST_SIZE 1
static inline unsigned char ddrphy_rdly_dq_rst_read(void) {
	unsigned char r = MMPTR(0xe0003808);
	return r;
}
static inline void ddrphy_rdly_dq_rst_write(unsigned char value) {
	MMPTR(0xe0003808) = value;
}
#define CSR_DDRPHY_RDLY_DQ_INC_ADDR 0xe0003810
#define CSR_DDRPHY_RDLY_DQ_INC_SIZE 1
static inline unsigned char ddrphy_rdly_dq_inc_read(void) {
	unsigned char r = MMPTR(0xe0003810);
	return r;
}
static inline void ddrphy_rdly_dq_inc_write(unsigned char value) {
	MMPTR(0xe0003810) = value;
}
#define CSR_DDRPHY_RDLY_DQ_BITSLIP_ADDR 0xe0003818
#define CSR_DDRPHY_RDLY_DQ_BITSLIP_SIZE 1
static inline unsigned char ddrphy_rdly_dq_bitslip_read(void) {
	unsigned char r = MMPTR(0xe0003818);
	return r;
}
static inline void ddrphy_rdly_dq_bitslip_write(unsigned char value) {
	MMPTR(0xe0003818) = value;
}

/* dfii */
#define CSR_DFII_BASE 0xe0002000
#define CSR_DFII_CONTROL_ADDR 0xe0002000
#define CSR_DFII_CONTROL_SIZE 1
static inline unsigned char dfii_control_read(void) {
	unsigned char r = MMPTR(0xe0002000);
	return r;
}
static inline void dfii_control_write(unsigned char value) {
	MMPTR(0xe0002000) = value;
}
#define CSR_DFII_PI0_COMMAND_ADDR 0xe0002008
#define CSR_DFII_PI0_COMMAND_SIZE 1
static inline unsigned char dfii_pi0_command_read(void) {
	unsigned char r = MMPTR(0xe0002008);
	return r;
}
static inline void dfii_pi0_command_write(unsigned char value) {
	MMPTR(0xe0002008) = value;
}
#define CSR_DFII_PI0_COMMAND_ISSUE_ADDR 0xe0002010
#define CSR_DFII_PI0_COMMAND_ISSUE_SIZE 1
static inline unsigned char dfii_pi0_command_issue_read(void) {
	unsigned char r = MMPTR(0xe0002010);
	return r;
}
static inline void dfii_pi0_command_issue_write(unsigned char value) {
	MMPTR(0xe0002010) = value;
}
#define CSR_DFII_PI0_ADDRESS_ADDR 0xe0002018
#define CSR_DFII_PI0_ADDRESS_SIZE 2
static inline unsigned short int dfii_pi0_address_read(void) {
	unsigned short int r = MMPTR(0xe0002018);
	r <<= 8;
	r |= MMPTR(0xe0002020);
	return r;
}
static inline void dfii_pi0_address_write(unsigned short int value) {
	MMPTR(0xe0002018) = value >> 8;
	MMPTR(0xe0002020) = value;
}
#define CSR_DFII_PI0_BADDRESS_ADDR 0xe0002028
#define CSR_DFII_PI0_BADDRESS_SIZE 1
static inline unsigned char dfii_pi0_baddress_read(void) {
	unsigned char r = MMPTR(0xe0002028);
	return r;
}
static inline void dfii_pi0_baddress_write(unsigned char value) {
	MMPTR(0xe0002028) = value;
}
#define CSR_DFII_PI0_WRDATA_ADDR 0xe0002030
#define CSR_DFII_PI0_WRDATA_SIZE 4
static inline unsigned int dfii_pi0_wrdata_read(void) {
	unsigned int r = MMPTR(0xe0002030);
	r <<= 8;
	r |= MMPTR(0xe0002038);
	r <<= 8;
	r |= MMPTR(0xe0002040);
	r <<= 8;
	r |= MMPTR(0xe0002048);
	return r;
}
static inline void dfii_pi0_wrdata_write(unsigned int value) {
	MMPTR(0xe0002030) = value >> 24;
	MMPTR(0xe0002038) = value >> 16;
	MMPTR(0xe0002040) = value >> 8;
	MMPTR(0xe0002048) = value;
}
#define CSR_DFII_PI0_RDDATA_ADDR 0xe0002050
#define CSR_DFII_PI0_RDDATA_SIZE 4
static inline unsigned int dfii_pi0_rddata_read(void) {
	unsigned int r = MMPTR(0xe0002050);
	r <<= 8;
	r |= MMPTR(0xe0002058);
	r <<= 8;
	r |= MMPTR(0xe0002060);
	r <<= 8;
	r |= MMPTR(0xe0002068);
	return r;
}
#define CSR_DFII_PI1_COMMAND_ADDR 0xe0002070
#define CSR_DFII_PI1_COMMAND_SIZE 1
static inline unsigned char dfii_pi1_command_read(void) {
	unsigned char r = MMPTR(0xe0002070);
	return r;
}
static inline void dfii_pi1_command_write(unsigned char value) {
	MMPTR(0xe0002070) = value;
}
#define CSR_DFII_PI1_COMMAND_ISSUE_ADDR 0xe0002078
#define CSR_DFII_PI1_COMMAND_ISSUE_SIZE 1
static inline unsigned char dfii_pi1_command_issue_read(void) {
	unsigned char r = MMPTR(0xe0002078);
	return r;
}
static inline void dfii_pi1_command_issue_write(unsigned char value) {
	MMPTR(0xe0002078) = value;
}
#define CSR_DFII_PI1_ADDRESS_ADDR 0xe0002080
#define CSR_DFII_PI1_ADDRESS_SIZE 2
static inline unsigned short int dfii_pi1_address_read(void) {
	unsigned short int r = MMPTR(0xe0002080);
	r <<= 8;
	r |= MMPTR(0xe0002088);
	return r;
}
static inline void dfii_pi1_address_write(unsigned short int value) {
	MMPTR(0xe0002080) = value >> 8;
	MMPTR(0xe0002088) = value;
}
#define CSR_DFII_PI1_BADDRESS_ADDR 0xe0002090
#define CSR_DFII_PI1_BADDRESS_SIZE 1
static inline unsigned char dfii_pi1_baddress_read(void) {
	unsigned char r = MMPTR(0xe0002090);
	return r;
}
static inline void dfii_pi1_baddress_write(unsigned char value) {
	MMPTR(0xe0002090) = value;
}
#define CSR_DFII_PI1_WRDATA_ADDR 0xe0002098
#define CSR_DFII_PI1_WRDATA_SIZE 4
static inline unsigned int dfii_pi1_wrdata_read(void) {
	unsigned int r = MMPTR(0xe0002098);
	r <<= 8;
	r |= MMPTR(0xe00020a0);
	r <<= 8;
	r |= MMPTR(0xe00020a8);
	r <<= 8;
	r |= MMPTR(0xe00020b0);
	return r;
}
static inline void dfii_pi1_wrdata_write(unsigned int value) {
	MMPTR(0xe0002098) = value >> 24;
	MMPTR(0xe00020a0) = value >> 16;
	MMPTR(0xe00020a8) = value >> 8;
	MMPTR(0xe00020b0) = value;
}
#define CSR_DFII_PI1_RDDATA_ADDR 0xe00020b8
#define CSR_DFII_PI1_RDDATA_SIZE 4
static inline unsigned int dfii_pi1_rddata_read(void) {
	unsigned int r = MMPTR(0xe00020b8);
	r <<= 8;
	r |= MMPTR(0xe00020c0);
	r <<= 8;
	r |= MMPTR(0xe00020c8);
	r <<= 8;
	r |= MMPTR(0xe00020d0);
	return r;
}
#define CSR_DFII_PI2_COMMAND_ADDR 0xe00020d8
#define CSR_DFII_PI2_COMMAND_SIZE 1
static inline unsigned char dfii_pi2_command_read(void) {
	unsigned char r = MMPTR(0xe00020d8);
	return r;
}
static inline void dfii_pi2_command_write(unsigned char value) {
	MMPTR(0xe00020d8) = value;
}
#define CSR_DFII_PI2_COMMAND_ISSUE_ADDR 0xe00020e0
#define CSR_DFII_PI2_COMMAND_ISSUE_SIZE 1
static inline unsigned char dfii_pi2_command_issue_read(void) {
	unsigned char r = MMPTR(0xe00020e0);
	return r;
}
static inline void dfii_pi2_command_issue_write(unsigned char value) {
	MMPTR(0xe00020e0) = value;
}
#define CSR_DFII_PI2_ADDRESS_ADDR 0xe00020e8
#define CSR_DFII_PI2_ADDRESS_SIZE 2
static inline unsigned short int dfii_pi2_address_read(void) {
	unsigned short int r = MMPTR(0xe00020e8);
	r <<= 8;
	r |= MMPTR(0xe00020f0);
	return r;
}
static inline void dfii_pi2_address_write(unsigned short int value) {
	MMPTR(0xe00020e8) = value >> 8;
	MMPTR(0xe00020f0) = value;
}
#define CSR_DFII_PI2_BADDRESS_ADDR 0xe00020f8
#define CSR_DFII_PI2_BADDRESS_SIZE 1
static inline unsigned char dfii_pi2_baddress_read(void) {
	unsigned char r = MMPTR(0xe00020f8);
	return r;
}
static inline void dfii_pi2_baddress_write(unsigned char value) {
	MMPTR(0xe00020f8) = value;
}
#define CSR_DFII_PI2_WRDATA_ADDR 0xe0002100
#define CSR_DFII_PI2_WRDATA_SIZE 4
static inline unsigned int dfii_pi2_wrdata_read(void) {
	unsigned int r = MMPTR(0xe0002100);
	r <<= 8;
	r |= MMPTR(0xe0002108);
	r <<= 8;
	r |= MMPTR(0xe0002110);
	r <<= 8;
	r |= MMPTR(0xe0002118);
	return r;
}
static inline void dfii_pi2_wrdata_write(unsigned int value) {
	MMPTR(0xe0002100) = value >> 24;
	MMPTR(0xe0002108) = value >> 16;
	MMPTR(0xe0002110) = value >> 8;
	MMPTR(0xe0002118) = value;
}
#define CSR_DFII_PI2_RDDATA_ADDR 0xe0002120
#define CSR_DFII_PI2_RDDATA_SIZE 4
static inline unsigned int dfii_pi2_rddata_read(void) {
	unsigned int r = MMPTR(0xe0002120);
	r <<= 8;
	r |= MMPTR(0xe0002128);
	r <<= 8;
	r |= MMPTR(0xe0002130);
	r <<= 8;
	r |= MMPTR(0xe0002138);
	return r;
}
#define CSR_DFII_PI3_COMMAND_ADDR 0xe0002140
#define CSR_DFII_PI3_COMMAND_SIZE 1
static inline unsigned char dfii_pi3_command_read(void) {
	unsigned char r = MMPTR(0xe0002140);
	return r;
}
static inline void dfii_pi3_command_write(unsigned char value) {
	MMPTR(0xe0002140) = value;
}
#define CSR_DFII_PI3_COMMAND_ISSUE_ADDR 0xe0002148
#define CSR_DFII_PI3_COMMAND_ISSUE_SIZE 1
static inline unsigned char dfii_pi3_command_issue_read(void) {
	unsigned char r = MMPTR(0xe0002148);
	return r;
}
static inline void dfii_pi3_command_issue_write(unsigned char value) {
	MMPTR(0xe0002148) = value;
}
#define CSR_DFII_PI3_ADDRESS_ADDR 0xe0002150
#define CSR_DFII_PI3_ADDRESS_SIZE 2
static inline unsigned short int dfii_pi3_address_read(void) {
	unsigned short int r = MMPTR(0xe0002150);
	r <<= 8;
	r |= MMPTR(0xe0002158);
	return r;
}
static inline void dfii_pi3_address_write(unsigned short int value) {
	MMPTR(0xe0002150) = value >> 8;
	MMPTR(0xe0002158) = value;
}
#define CSR_DFII_PI3_BADDRESS_ADDR 0xe0002160
#define CSR_DFII_PI3_BADDRESS_SIZE 1
static inline unsigned char dfii_pi3_baddress_read(void) {
	unsigned char r = MMPTR(0xe0002160);
	return r;
}
static inline void dfii_pi3_baddress_write(unsigned char value) {
	MMPTR(0xe0002160) = value;
}
#define CSR_DFII_PI3_WRDATA_ADDR 0xe0002168
#define CSR_DFII_PI3_WRDATA_SIZE 4
static inline unsigned int dfii_pi3_wrdata_read(void) {
	unsigned int r = MMPTR(0xe0002168);
	r <<= 8;
	r |= MMPTR(0xe0002170);
	r <<= 8;
	r |= MMPTR(0xe0002178);
	r <<= 8;
	r |= MMPTR(0xe0002180);
	return r;
}
static inline void dfii_pi3_wrdata_write(unsigned int value) {
	MMPTR(0xe0002168) = value >> 24;
	MMPTR(0xe0002170) = value >> 16;
	MMPTR(0xe0002178) = value >> 8;
	MMPTR(0xe0002180) = value;
}
#define CSR_DFII_PI3_RDDATA_ADDR 0xe0002188
#define CSR_DFII_PI3_RDDATA_SIZE 4
static inline unsigned int dfii_pi3_rddata_read(void) {
	unsigned int r = MMPTR(0xe0002188);
	r <<= 8;
	r |= MMPTR(0xe0002190);
	r <<= 8;
	r |= MMPTR(0xe0002198);
	r <<= 8;
	r |= MMPTR(0xe00021a0);
	return r;
}

/* error_led */
#define CSR_ERROR_LED_BASE 0xe0007000
#define CSR_ERROR_LED_OUT_ADDR 0xe0007000
#define CSR_ERROR_LED_OUT_SIZE 1
static inline unsigned char error_led_out_read(void) {
	unsigned char r = MMPTR(0xe0007000);
	return r;
}
static inline void error_led_out_write(unsigned char value) {
	MMPTR(0xe0007000) = value;
}

/* ethmac */
#define CSR_ETHMAC_BASE 0xe0006000
#define CSR_ETHMAC_SRAM_WRITER_SLOT_ADDR 0xe0006000
#define CSR_ETHMAC_SRAM_WRITER_SLOT_SIZE 1
static inline unsigned char ethmac_sram_writer_slot_read(void) {
	unsigned char r = MMPTR(0xe0006000);
	return r;
}
#define CSR_ETHMAC_SRAM_WRITER_LENGTH_ADDR 0xe0006008
#define CSR_ETHMAC_SRAM_WRITER_LENGTH_SIZE 2
static inline unsigned short int ethmac_sram_writer_length_read(void) {
	unsigned short int r = MMPTR(0xe0006008);
	r <<= 8;
	r |= MMPTR(0xe0006010);
	return r;
}
#define CSR_ETHMAC_SRAM_WRITER_ERRORS_ADDR 0xe0006018
#define CSR_ETHMAC_SRAM_WRITER_ERRORS_SIZE 4
static inline unsigned int ethmac_sram_writer_errors_read(void) {
	unsigned int r = MMPTR(0xe0006018);
	r <<= 8;
	r |= MMPTR(0xe0006020);
	r <<= 8;
	r |= MMPTR(0xe0006028);
	r <<= 8;
	r |= MMPTR(0xe0006030);
	return r;
}
#define CSR_ETHMAC_SRAM_WRITER_EV_STATUS_ADDR 0xe0006038
#define CSR_ETHMAC_SRAM_WRITER_EV_STATUS_SIZE 1
static inline unsigned char ethmac_sram_writer_ev_status_read(void) {
	unsigned char r = MMPTR(0xe0006038);
	return r;
}
static inline void ethmac_sram_writer_ev_status_write(unsigned char value) {
	MMPTR(0xe0006038) = value;
}
#define CSR_ETHMAC_SRAM_WRITER_EV_PENDING_ADDR 0xe0006040
#define CSR_ETHMAC_SRAM_WRITER_EV_PENDING_SIZE 1
static inline unsigned char ethmac_sram_writer_ev_pending_read(void) {
	unsigned char r = MMPTR(0xe0006040);
	return r;
}
static inline void ethmac_sram_writer_ev_pending_write(unsigned char value) {
	MMPTR(0xe0006040) = value;
}
#define CSR_ETHMAC_SRAM_WRITER_EV_ENABLE_ADDR 0xe0006048
#define CSR_ETHMAC_SRAM_WRITER_EV_ENABLE_SIZE 1
static inline unsigned char ethmac_sram_writer_ev_enable_read(void) {
	unsigned char r = MMPTR(0xe0006048);
	return r;
}
static inline void ethmac_sram_writer_ev_enable_write(unsigned char value) {
	MMPTR(0xe0006048) = value;
}
#define CSR_ETHMAC_SRAM_READER_START_ADDR 0xe0006050
#define CSR_ETHMAC_SRAM_READER_START_SIZE 1
static inline unsigned char ethmac_sram_reader_start_read(void) {
	unsigned char r = MMPTR(0xe0006050);
	return r;
}
static inline void ethmac_sram_reader_start_write(unsigned char value) {
	MMPTR(0xe0006050) = value;
}
#define CSR_ETHMAC_SRAM_READER_READY_ADDR 0xe0006058
#define CSR_ETHMAC_SRAM_READER_READY_SIZE 1
static inline unsigned char ethmac_sram_reader_ready_read(void) {
	unsigned char r = MMPTR(0xe0006058);
	return r;
}
#define CSR_ETHMAC_SRAM_READER_SLOT_ADDR 0xe0006060
#define CSR_ETHMAC_SRAM_READER_SLOT_SIZE 1
static inline unsigned char ethmac_sram_reader_slot_read(void) {
	unsigned char r = MMPTR(0xe0006060);
	return r;
}
static inline void ethmac_sram_reader_slot_write(unsigned char value) {
	MMPTR(0xe0006060) = value;
}
#define CSR_ETHMAC_SRAM_READER_LENGTH_ADDR 0xe0006068
#define CSR_ETHMAC_SRAM_READER_LENGTH_SIZE 2
static inline unsigned short int ethmac_sram_reader_length_read(void) {
	unsigned short int r = MMPTR(0xe0006068);
	r <<= 8;
	r |= MMPTR(0xe0006070);
	return r;
}
static inline void ethmac_sram_reader_length_write(unsigned short int value) {
	MMPTR(0xe0006068) = value >> 8;
	MMPTR(0xe0006070) = value;
}
#define CSR_ETHMAC_SRAM_READER_EV_STATUS_ADDR 0xe0006078
#define CSR_ETHMAC_SRAM_READER_EV_STATUS_SIZE 1
static inline unsigned char ethmac_sram_reader_ev_status_read(void) {
	unsigned char r = MMPTR(0xe0006078);
	return r;
}
static inline void ethmac_sram_reader_ev_status_write(unsigned char value) {
	MMPTR(0xe0006078) = value;
}
#define CSR_ETHMAC_SRAM_READER_EV_PENDING_ADDR 0xe0006080
#define CSR_ETHMAC_SRAM_READER_EV_PENDING_SIZE 1
static inline unsigned char ethmac_sram_reader_ev_pending_read(void) {
	unsigned char r = MMPTR(0xe0006080);
	return r;
}
static inline void ethmac_sram_reader_ev_pending_write(unsigned char value) {
	MMPTR(0xe0006080) = value;
}
#define CSR_ETHMAC_SRAM_READER_EV_ENABLE_ADDR 0xe0006088
#define CSR_ETHMAC_SRAM_READER_EV_ENABLE_SIZE 1
static inline unsigned char ethmac_sram_reader_ev_enable_read(void) {
	unsigned char r = MMPTR(0xe0006088);
	return r;
}
static inline void ethmac_sram_reader_ev_enable_write(unsigned char value) {
	MMPTR(0xe0006088) = value;
}
#define CSR_ETHMAC_PREAMBLE_ERRORS_ADDR 0xe0006090
#define CSR_ETHMAC_PREAMBLE_ERRORS_SIZE 4
static inline unsigned int ethmac_preamble_errors_read(void) {
	unsigned int r = MMPTR(0xe0006090);
	r <<= 8;
	r |= MMPTR(0xe0006098);
	r <<= 8;
	r |= MMPTR(0xe00060a0);
	r <<= 8;
	r |= MMPTR(0xe00060a8);
	return r;
}
#define CSR_ETHMAC_CRC_ERRORS_ADDR 0xe00060b0
#define CSR_ETHMAC_CRC_ERRORS_SIZE 4
static inline unsigned int ethmac_crc_errors_read(void) {
	unsigned int r = MMPTR(0xe00060b0);
	r <<= 8;
	r |= MMPTR(0xe00060b8);
	r <<= 8;
	r |= MMPTR(0xe00060c0);
	r <<= 8;
	r |= MMPTR(0xe00060c8);
	return r;
}

/* i2c */
#define CSR_I2C_BASE 0xe0007800
#define CSR_I2C_IN_ADDR 0xe0007800
#define CSR_I2C_IN_SIZE 1
static inline unsigned char i2c_in_read(void) {
	unsigned char r = MMPTR(0xe0007800);
	return r;
}
#define CSR_I2C_OUT_ADDR 0xe0007808
#define CSR_I2C_OUT_SIZE 1
static inline unsigned char i2c_out_read(void) {
	unsigned char r = MMPTR(0xe0007808);
	return r;
}
static inline void i2c_out_write(unsigned char value) {
	MMPTR(0xe0007808) = value;
}
#define CSR_I2C_OE_ADDR 0xe0007810
#define CSR_I2C_OE_SIZE 1
static inline unsigned char i2c_oe_read(void) {
	unsigned char r = MMPTR(0xe0007810);
	return r;
}
static inline void i2c_oe_write(unsigned char value) {
	MMPTR(0xe0007810) = value;
}

/* icap */
#define CSR_ICAP_BASE 0xe0005000
#define CSR_ICAP_IPROG_ADDR 0xe0005000
#define CSR_ICAP_IPROG_SIZE 1
static inline unsigned char icap_iprog_read(void) {
	unsigned char r = MMPTR(0xe0005000);
	return r;
}
static inline void icap_iprog_write(unsigned char value) {
	MMPTR(0xe0005000) = value;
}

/* identifier */
#define CSR_IDENTIFIER_BASE 0xe0001000
#define CSR_IDENTIFIER_ADDRESS_ADDR 0xe0001000
#define CSR_IDENTIFIER_ADDRESS_SIZE 1
static inline unsigned char identifier_address_read(void) {
	unsigned char r = MMPTR(0xe0001000);
	return r;
}
static inline void identifier_address_write(unsigned char value) {
	MMPTR(0xe0001000) = value;
}
#define CSR_IDENTIFIER_DATA_ADDR 0xe0001008
#define CSR_IDENTIFIER_DATA_SIZE 1
static inline unsigned char identifier_data_read(void) {
	unsigned char r = MMPTR(0xe0001008);
	return r;
}

/* kernel_cpu */
#define CSR_KERNEL_CPU_BASE 0xe0006800
#define CSR_KERNEL_CPU_RESET_ADDR 0xe0006800
#define CSR_KERNEL_CPU_RESET_SIZE 1
static inline unsigned char kernel_cpu_reset_read(void) {
	unsigned char r = MMPTR(0xe0006800);
	return r;
}
static inline void kernel_cpu_reset_write(unsigned char value) {
	MMPTR(0xe0006800) = value;
}

/* rtio_analyzer */
#define CSR_RTIO_ANALYZER_BASE 0xe0009000
#define CSR_RTIO_ANALYZER_ENABLE_ADDR 0xe0009000
#define CSR_RTIO_ANALYZER_ENABLE_SIZE 1
static inline unsigned char rtio_analyzer_enable_read(void) {
	unsigned char r = MMPTR(0xe0009000);
	return r;
}
static inline void rtio_analyzer_enable_write(unsigned char value) {
	MMPTR(0xe0009000) = value;
}
#define CSR_RTIO_ANALYZER_BUSY_ADDR 0xe0009008
#define CSR_RTIO_ANALYZER_BUSY_SIZE 1
static inline unsigned char rtio_analyzer_busy_read(void) {
	unsigned char r = MMPTR(0xe0009008);
	return r;
}
#define CSR_RTIO_ANALYZER_MESSAGE_ENCODER_OVERFLOW_ADDR 0xe0009010
#define CSR_RTIO_ANALYZER_MESSAGE_ENCODER_OVERFLOW_SIZE 1
static inline unsigned char rtio_analyzer_message_encoder_overflow_read(void) {
	unsigned char r = MMPTR(0xe0009010);
	return r;
}
#define CSR_RTIO_ANALYZER_MESSAGE_ENCODER_OVERFLOW_RESET_ADDR 0xe0009018
#define CSR_RTIO_ANALYZER_MESSAGE_ENCODER_OVERFLOW_RESET_SIZE 1
static inline unsigned char rtio_analyzer_message_encoder_overflow_reset_read(void) {
	unsigned char r = MMPTR(0xe0009018);
	return r;
}
static inline void rtio_analyzer_message_encoder_overflow_reset_write(unsigned char value) {
	MMPTR(0xe0009018) = value;
}
#define CSR_RTIO_ANALYZER_DMA_RESET_ADDR 0xe0009020
#define CSR_RTIO_ANALYZER_DMA_RESET_SIZE 1
static inline unsigned char rtio_analyzer_dma_reset_read(void) {
	unsigned char r = MMPTR(0xe0009020);
	return r;
}
static inline void rtio_analyzer_dma_reset_write(unsigned char value) {
	MMPTR(0xe0009020) = value;
}
#define CSR_RTIO_ANALYZER_DMA_BASE_ADDRESS_ADDR 0xe0009028
#define CSR_RTIO_ANALYZER_DMA_BASE_ADDRESS_SIZE 5
static inline unsigned long long int rtio_analyzer_dma_base_address_read(void) {
	unsigned long long int r = MMPTR(0xe0009028);
	r <<= 8;
	r |= MMPTR(0xe0009030);
	r <<= 8;
	r |= MMPTR(0xe0009038);
	r <<= 8;
	r |= MMPTR(0xe0009040);
	r <<= 8;
	r |= MMPTR(0xe0009048);
	return r;
}
static inline void rtio_analyzer_dma_base_address_write(unsigned long long int value) {
	MMPTR(0xe0009028) = value >> 32;
	MMPTR(0xe0009030) = value >> 24;
	MMPTR(0xe0009038) = value >> 16;
	MMPTR(0xe0009040) = value >> 8;
	MMPTR(0xe0009048) = value;
}
#define CSR_RTIO_ANALYZER_DMA_LAST_ADDRESS_ADDR 0xe0009050
#define CSR_RTIO_ANALYZER_DMA_LAST_ADDRESS_SIZE 5
static inline unsigned long long int rtio_analyzer_dma_last_address_read(void) {
	unsigned long long int r = MMPTR(0xe0009050);
	r <<= 8;
	r |= MMPTR(0xe0009058);
	r <<= 8;
	r |= MMPTR(0xe0009060);
	r <<= 8;
	r |= MMPTR(0xe0009068);
	r <<= 8;
	r |= MMPTR(0xe0009070);
	return r;
}
static inline void rtio_analyzer_dma_last_address_write(unsigned long long int value) {
	MMPTR(0xe0009050) = value >> 32;
	MMPTR(0xe0009058) = value >> 24;
	MMPTR(0xe0009060) = value >> 16;
	MMPTR(0xe0009068) = value >> 8;
	MMPTR(0xe0009070) = value;
}
#define CSR_RTIO_ANALYZER_DMA_BYTE_COUNT_ADDR 0xe0009078
#define CSR_RTIO_ANALYZER_DMA_BYTE_COUNT_SIZE 8
static inline unsigned long long int rtio_analyzer_dma_byte_count_read(void) {
	unsigned long long int r = MMPTR(0xe0009078);
	r <<= 8;
	r |= MMPTR(0xe0009080);
	r <<= 8;
	r |= MMPTR(0xe0009088);
	r <<= 8;
	r |= MMPTR(0xe0009090);
	r <<= 8;
	r |= MMPTR(0xe0009098);
	r <<= 8;
	r |= MMPTR(0xe00090a0);
	r <<= 8;
	r |= MMPTR(0xe00090a8);
	r <<= 8;
	r |= MMPTR(0xe00090b0);
	return r;
}

/* rtio_core */
#define CSR_RTIO_CORE_BASE 0xe0008000
#define CSR_RTIO_CORE_RESET_ADDR 0xe0008000
#define CSR_RTIO_CORE_RESET_SIZE 1
static inline unsigned char rtio_core_reset_read(void) {
	unsigned char r = MMPTR(0xe0008000);
	return r;
}
static inline void rtio_core_reset_write(unsigned char value) {
	MMPTR(0xe0008000) = value;
}
#define CSR_RTIO_CORE_RESET_PHY_ADDR 0xe0008008
#define CSR_RTIO_CORE_RESET_PHY_SIZE 1
static inline unsigned char rtio_core_reset_phy_read(void) {
	unsigned char r = MMPTR(0xe0008008);
	return r;
}
static inline void rtio_core_reset_phy_write(unsigned char value) {
	MMPTR(0xe0008008) = value;
}
#define CSR_RTIO_CORE_SED_SPREAD_ENABLE_ADDR 0xe0008010
#define CSR_RTIO_CORE_SED_SPREAD_ENABLE_SIZE 1
static inline unsigned char rtio_core_sed_spread_enable_read(void) {
	unsigned char r = MMPTR(0xe0008010);
	return r;
}
static inline void rtio_core_sed_spread_enable_write(unsigned char value) {
	MMPTR(0xe0008010) = value;
}
#define CSR_RTIO_CORE_ASYNC_ERROR_ADDR 0xe0008018
#define CSR_RTIO_CORE_ASYNC_ERROR_SIZE 1
static inline unsigned char rtio_core_async_error_read(void) {
	unsigned char r = MMPTR(0xe0008018);
	return r;
}
static inline void rtio_core_async_error_write(unsigned char value) {
	MMPTR(0xe0008018) = value;
}
#define CSR_RTIO_CORE_COLLISION_CHANNEL_ADDR 0xe0008020
#define CSR_RTIO_CORE_COLLISION_CHANNEL_SIZE 2
static inline unsigned short int rtio_core_collision_channel_read(void) {
	unsigned short int r = MMPTR(0xe0008020);
	r <<= 8;
	r |= MMPTR(0xe0008028);
	return r;
}
#define CSR_RTIO_CORE_BUSY_CHANNEL_ADDR 0xe0008030
#define CSR_RTIO_CORE_BUSY_CHANNEL_SIZE 2
static inline unsigned short int rtio_core_busy_channel_read(void) {
	unsigned short int r = MMPTR(0xe0008030);
	r <<= 8;
	r |= MMPTR(0xe0008038);
	return r;
}
#define CSR_RTIO_CORE_SEQUENCE_ERROR_CHANNEL_ADDR 0xe0008040
#define CSR_RTIO_CORE_SEQUENCE_ERROR_CHANNEL_SIZE 2
static inline unsigned short int rtio_core_sequence_error_channel_read(void) {
	unsigned short int r = MMPTR(0xe0008040);
	r <<= 8;
	r |= MMPTR(0xe0008048);
	return r;
}

/* rtio_moninj */
#define CSR_RTIO_MONINJ_BASE 0xe0008800
#define CSR_RTIO_MONINJ_MON_CHAN_SEL_ADDR 0xe0008800
#define CSR_RTIO_MONINJ_MON_CHAN_SEL_SIZE 1
static inline unsigned char rtio_moninj_mon_chan_sel_read(void) {
	unsigned char r = MMPTR(0xe0008800);
	return r;
}
static inline void rtio_moninj_mon_chan_sel_write(unsigned char value) {
	MMPTR(0xe0008800) = value;
}
#define CSR_RTIO_MONINJ_MON_PROBE_SEL_ADDR 0xe0008808
#define CSR_RTIO_MONINJ_MON_PROBE_SEL_SIZE 1
static inline unsigned char rtio_moninj_mon_probe_sel_read(void) {
	unsigned char r = MMPTR(0xe0008808);
	return r;
}
static inline void rtio_moninj_mon_probe_sel_write(unsigned char value) {
	MMPTR(0xe0008808) = value;
}
#define CSR_RTIO_MONINJ_MON_VALUE_UPDATE_ADDR 0xe0008810
#define CSR_RTIO_MONINJ_MON_VALUE_UPDATE_SIZE 1
static inline unsigned char rtio_moninj_mon_value_update_read(void) {
	unsigned char r = MMPTR(0xe0008810);
	return r;
}
static inline void rtio_moninj_mon_value_update_write(unsigned char value) {
	MMPTR(0xe0008810) = value;
}
#define CSR_RTIO_MONINJ_MON_VALUE_ADDR 0xe0008818
#define CSR_RTIO_MONINJ_MON_VALUE_SIZE 4
static inline unsigned int rtio_moninj_mon_value_read(void) {
	unsigned int r = MMPTR(0xe0008818);
	r <<= 8;
	r |= MMPTR(0xe0008820);
	r <<= 8;
	r |= MMPTR(0xe0008828);
	r <<= 8;
	r |= MMPTR(0xe0008830);
	return r;
}
#define CSR_RTIO_MONINJ_INJ_CHAN_SEL_ADDR 0xe0008838
#define CSR_RTIO_MONINJ_INJ_CHAN_SEL_SIZE 1
static inline unsigned char rtio_moninj_inj_chan_sel_read(void) {
	unsigned char r = MMPTR(0xe0008838);
	return r;
}
static inline void rtio_moninj_inj_chan_sel_write(unsigned char value) {
	MMPTR(0xe0008838) = value;
}
#define CSR_RTIO_MONINJ_INJ_OVERRIDE_SEL_ADDR 0xe0008840
#define CSR_RTIO_MONINJ_INJ_OVERRIDE_SEL_SIZE 1
static inline unsigned char rtio_moninj_inj_override_sel_read(void) {
	unsigned char r = MMPTR(0xe0008840);
	return r;
}
static inline void rtio_moninj_inj_override_sel_write(unsigned char value) {
	MMPTR(0xe0008840) = value;
}
#define CSR_RTIO_MONINJ_INJ_VALUE_ADDR 0xe0008848
#define CSR_RTIO_MONINJ_INJ_VALUE_SIZE 1
static inline unsigned char rtio_moninj_inj_value_read(void) {
	unsigned char r = MMPTR(0xe0008848);
	return r;
}
static inline void rtio_moninj_inj_value_write(unsigned char value) {
	MMPTR(0xe0008848) = value;
}

/* spiflash */
#define CSR_SPIFLASH_BASE 0xe0004800
#define CSR_SPIFLASH_BITBANG_ADDR 0xe0004800
#define CSR_SPIFLASH_BITBANG_SIZE 1
static inline unsigned char spiflash_bitbang_read(void) {
	unsigned char r = MMPTR(0xe0004800);
	return r;
}
static inline void spiflash_bitbang_write(unsigned char value) {
	MMPTR(0xe0004800) = value;
}
#define CSR_SPIFLASH_MISO_ADDR 0xe0004808
#define CSR_SPIFLASH_MISO_SIZE 1
static inline unsigned char spiflash_miso_read(void) {
	unsigned char r = MMPTR(0xe0004808);
	return r;
}
#define CSR_SPIFLASH_BITBANG_EN_ADDR 0xe0004810
#define CSR_SPIFLASH_BITBANG_EN_SIZE 1
static inline unsigned char spiflash_bitbang_en_read(void) {
	unsigned char r = MMPTR(0xe0004810);
	return r;
}
static inline void spiflash_bitbang_en_write(unsigned char value) {
	MMPTR(0xe0004810) = value;
}

/* timer0 */
#define CSR_TIMER0_BASE 0xe0001800
#define CSR_TIMER0_LOAD_ADDR 0xe0001800
#define CSR_TIMER0_LOAD_SIZE 8
static inline unsigned long long int timer0_load_read(void) {
	unsigned long long int r = MMPTR(0xe0001800);
	r <<= 8;
	r |= MMPTR(0xe0001808);
	r <<= 8;
	r |= MMPTR(0xe0001810);
	r <<= 8;
	r |= MMPTR(0xe0001818);
	r <<= 8;
	r |= MMPTR(0xe0001820);
	r <<= 8;
	r |= MMPTR(0xe0001828);
	r <<= 8;
	r |= MMPTR(0xe0001830);
	r <<= 8;
	r |= MMPTR(0xe0001838);
	return r;
}
static inline void timer0_load_write(unsigned long long int value) {
	MMPTR(0xe0001800) = value >> 56;
	MMPTR(0xe0001808) = value >> 48;
	MMPTR(0xe0001810) = value >> 40;
	MMPTR(0xe0001818) = value >> 32;
	MMPTR(0xe0001820) = value >> 24;
	MMPTR(0xe0001828) = value >> 16;
	MMPTR(0xe0001830) = value >> 8;
	MMPTR(0xe0001838) = value;
}
#define CSR_TIMER0_RELOAD_ADDR 0xe0001840
#define CSR_TIMER0_RELOAD_SIZE 8
static inline unsigned long long int timer0_reload_read(void) {
	unsigned long long int r = MMPTR(0xe0001840);
	r <<= 8;
	r |= MMPTR(0xe0001848);
	r <<= 8;
	r |= MMPTR(0xe0001850);
	r <<= 8;
	r |= MMPTR(0xe0001858);
	r <<= 8;
	r |= MMPTR(0xe0001860);
	r <<= 8;
	r |= MMPTR(0xe0001868);
	r <<= 8;
	r |= MMPTR(0xe0001870);
	r <<= 8;
	r |= MMPTR(0xe0001878);
	return r;
}
static inline void timer0_reload_write(unsigned long long int value) {
	MMPTR(0xe0001840) = value >> 56;
	MMPTR(0xe0001848) = value >> 48;
	MMPTR(0xe0001850) = value >> 40;
	MMPTR(0xe0001858) = value >> 32;
	MMPTR(0xe0001860) = value >> 24;
	MMPTR(0xe0001868) = value >> 16;
	MMPTR(0xe0001870) = value >> 8;
	MMPTR(0xe0001878) = value;
}
#define CSR_TIMER0_EN_ADDR 0xe0001880
#define CSR_TIMER0_EN_SIZE 1
static inline unsigned char timer0_en_read(void) {
	unsigned char r = MMPTR(0xe0001880);
	return r;
}
static inline void timer0_en_write(unsigned char value) {
	MMPTR(0xe0001880) = value;
}
#define CSR_TIMER0_UPDATE_VALUE_ADDR 0xe0001888
#define CSR_TIMER0_UPDATE_VALUE_SIZE 1
static inline unsigned char timer0_update_value_read(void) {
	unsigned char r = MMPTR(0xe0001888);
	return r;
}
static inline void timer0_update_value_write(unsigned char value) {
	MMPTR(0xe0001888) = value;
}
#define CSR_TIMER0_VALUE_ADDR 0xe0001890
#define CSR_TIMER0_VALUE_SIZE 8
static inline unsigned long long int timer0_value_read(void) {
	unsigned long long int r = MMPTR(0xe0001890);
	r <<= 8;
	r |= MMPTR(0xe0001898);
	r <<= 8;
	r |= MMPTR(0xe00018a0);
	r <<= 8;
	r |= MMPTR(0xe00018a8);
	r <<= 8;
	r |= MMPTR(0xe00018b0);
	r <<= 8;
	r |= MMPTR(0xe00018b8);
	r <<= 8;
	r |= MMPTR(0xe00018c0);
	r <<= 8;
	r |= MMPTR(0xe00018c8);
	return r;
}
#define CSR_TIMER0_EV_STATUS_ADDR 0xe00018d0
#define CSR_TIMER0_EV_STATUS_SIZE 1
static inline unsigned char timer0_ev_status_read(void) {
	unsigned char r = MMPTR(0xe00018d0);
	return r;
}
static inline void timer0_ev_status_write(unsigned char value) {
	MMPTR(0xe00018d0) = value;
}
#define CSR_TIMER0_EV_PENDING_ADDR 0xe00018d8
#define CSR_TIMER0_EV_PENDING_SIZE 1
static inline unsigned char timer0_ev_pending_read(void) {
	unsigned char r = MMPTR(0xe00018d8);
	return r;
}
static inline void timer0_ev_pending_write(unsigned char value) {
	MMPTR(0xe00018d8) = value;
}
#define CSR_TIMER0_EV_ENABLE_ADDR 0xe00018e0
#define CSR_TIMER0_EV_ENABLE_SIZE 1
static inline unsigned char timer0_ev_enable_read(void) {
	unsigned char r = MMPTR(0xe00018e0);
	return r;
}
static inline void timer0_ev_enable_write(unsigned char value) {
	MMPTR(0xe00018e0) = value;
}

/* uart */
#define CSR_UART_BASE 0xe0000800
#define CSR_UART_RXTX_ADDR 0xe0000800
#define CSR_UART_RXTX_SIZE 1
static inline unsigned char uart_rxtx_read(void) {
	unsigned char r = MMPTR(0xe0000800);
	return r;
}
static inline void uart_rxtx_write(unsigned char value) {
	MMPTR(0xe0000800) = value;
}
#define CSR_UART_TXFULL_ADDR 0xe0000808
#define CSR_UART_TXFULL_SIZE 1
static inline unsigned char uart_txfull_read(void) {
	unsigned char r = MMPTR(0xe0000808);
	return r;
}
#define CSR_UART_RXEMPTY_ADDR 0xe0000810
#define CSR_UART_RXEMPTY_SIZE 1
static inline unsigned char uart_rxempty_read(void) {
	unsigned char r = MMPTR(0xe0000810);
	return r;
}
#define CSR_UART_EV_STATUS_ADDR 0xe0000818
#define CSR_UART_EV_STATUS_SIZE 1
static inline unsigned char uart_ev_status_read(void) {
	unsigned char r = MMPTR(0xe0000818);
	return r;
}
static inline void uart_ev_status_write(unsigned char value) {
	MMPTR(0xe0000818) = value;
}
#define CSR_UART_EV_PENDING_ADDR 0xe0000820
#define CSR_UART_EV_PENDING_SIZE 1
static inline unsigned char uart_ev_pending_read(void) {
	unsigned char r = MMPTR(0xe0000820);
	return r;
}
static inline void uart_ev_pending_write(unsigned char value) {
	MMPTR(0xe0000820) = value;
}
#define CSR_UART_EV_ENABLE_ADDR 0xe0000828
#define CSR_UART_EV_ENABLE_SIZE 1
static inline unsigned char uart_ev_enable_read(void) {
	unsigned char r = MMPTR(0xe0000828);
	return r;
}
static inline void uart_ev_enable_write(unsigned char value) {
	MMPTR(0xe0000828) = value;
}

/* uart_phy */
#define CSR_UART_PHY_BASE 0xe0000000
#define CSR_UART_PHY_TUNING_WORD_ADDR 0xe0000000
#define CSR_UART_PHY_TUNING_WORD_SIZE 4
static inline unsigned int uart_phy_tuning_word_read(void) {
	unsigned int r = MMPTR(0xe0000000);
	r <<= 8;
	r |= MMPTR(0xe0000008);
	r <<= 8;
	r |= MMPTR(0xe0000010);
	r <<= 8;
	r |= MMPTR(0xe0000018);
	return r;
}
static inline void uart_phy_tuning_word_write(unsigned int value) {
	MMPTR(0xe0000000) = value >> 24;
	MMPTR(0xe0000008) = value >> 16;
	MMPTR(0xe0000010) = value >> 8;
	MMPTR(0xe0000018) = value;
}

/* virtual_leds */
#define CSR_VIRTUAL_LEDS_BASE 0xe0004000
#define CSR_VIRTUAL_LEDS_STATUS_ADDR 0xe0004000
#define CSR_VIRTUAL_LEDS_STATUS_SIZE 1
static inline unsigned char virtual_leds_status_read(void) {
	unsigned char r = MMPTR(0xe0004000);
	return r;
}

/* constants */
#define UART_INTERRUPT 0
static inline int uart_interrupt_read(void) {
	return 0;
}
#define TIMER0_INTERRUPT 1
static inline int timer0_interrupt_read(void) {
	return 1;
}
#define ETHMAC_INTERRUPT 2
static inline int ethmac_interrupt_read(void) {
	return 2;
}
#define ETHMAC_CORE_PREAMBLE_CRC 1
static inline int ethmac_core_preamble_crc_read(void) {
	return 1;
}
#define ETHMAC_RX_SLOTS 4
static inline int ethmac_rx_slots_read(void) {
	return 4;
}
#define ETHMAC_TX_SLOTS 4
static inline int ethmac_tx_slots_read(void) {
	return 4;
}
#define ETHMAC_SLOT_SIZE 2048
static inline int ethmac_slot_size_read(void) {
	return 2048;
}
#define CONFIG_CLOCK_FREQUENCY 125000000
static inline int config_clock_frequency_read(void) {
	return 125000000;
}
#define CONFIG_DATA_WIDTH_BYTES 8
static inline int config_data_width_bytes_read(void) {
	return 8;
}
#define CONFIG_DRTIO_ROLE "standalone"
static inline const char * config_drtio_role_read(void) {
	return "standalone";
}
#define CONFIG_HAS_RTIO_LOG
#define CONFIG_HAS_SI5324
#define CONFIG_HW_REV "v2.0"
static inline const char * config_hw_rev_read(void) {
	return "v2.0";
}
#define CONFIG_I2C_BUS_COUNT 1
static inline int config_i2c_bus_count_read(void) {
	return 1;
}
#define CONFIG_IDENTIFIER_STR "9.0+unknown.beta;testbed"
static inline const char * config_identifier_str_read(void) {
	return "9.0+unknown.beta;testbed";
}
#define CONFIG_L2_SIZE 131072
static inline int config_l2_size_read(void) {
	return 131072;
}
#define CONFIG_RTIO_FREQUENCY "125.0"
static inline const char * config_rtio_frequency_read(void) {
	return "125.0";
}
#define CONFIG_RTIO_LOG_CHANNEL 37
static inline int config_rtio_log_channel_read(void) {
	return 37;
}
#define CONFIG_SI5324_SOFT_RESET
#define CONFIG_SOC_PLATFORM "kasli"
static inline const char * config_soc_platform_read(void) {
	return "kasli";
}
#define CONFIG_SPIFLASH_PAGE_SIZE 256
static inline int config_spiflash_page_size_read(void) {
	return 256;
}
#define CONFIG_SPIFLASH_SECTOR_SIZE 65536
static inline int config_spiflash_sector_size_read(void) {
	return 65536;
}
#define CONFIG_KERNEL_HAS_CRI_CON
#define CONFIG_KERNEL_HAS_RTIO
#define CONFIG_KERNEL_HAS_RTIO_DMA

#endif
