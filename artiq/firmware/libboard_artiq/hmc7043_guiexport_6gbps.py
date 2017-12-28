# glbl_cfg1_swrst[0:0] = 0x0
dut.write(0x0, 0x0)

# glbl_cfg1_sleep[0:0] = 0x0
# glbl_cfg1_restart[1:1] = 0x0
# sysr_cfg1_pulsor_req[2:2] = 0x0
# grpx_cfg1_mute[3:3] = 0x0
# dist_cfg1_perf_floor[6:6] = 0x0
# sysr_cfg1_reseed_req[7:7] = 0x0
dut.write(0x1, 0x0)

# sysr_cfg1_rev[0:0] = 0x0
# sysr_cfg1_slipN_req[1:1] = 0x0
dut.write(0x2, 0x0)

# glbl_cfg1_ena_sysr[2:2] = 0x1
# glbl_cfg2_ena_vcos[4:3] = 0x0
# glbl_cfg1_ena_sysri[5:5] = 0x1
dut.write(0x3, 0x24)

# glbl_cfg7_ena_clkgr[6:0] = 0x3B
dut.write(0x4, 0x3B)

# glbl_cfg1_clear_alarms[0:0] = 0x0
dut.write(0x6, 0x0)

# glbl_reserved[0:0] = 0x0
dut.write(0x7, 0x0)

# glbl_cfg5_ibuf0_en[0:0] = 0x0
# glbl_cfg5_ibuf0_mode[4:1] = 0x7
dut.write(0xA, 0xE)

# glbl_cfg5_ibuf1_en[0:0] = 0x1
# glbl_cfg5_ibuf1_mode[4:1] = 0x7
dut.write(0xB, 0xF)

# glbl_cfg5_gpi1_en[0:0] = 0x0
# glbl_cfg5_gpi1_sel[4:1] = 0x0
dut.write(0x46, 0x0)

# glbl_cfg8_gpo1_en[0:0] = 0x1
# glbl_cfg8_gpo1_mode[1:1] = 0x1
# glbl_cfg8_gpo1_sel[7:2] = 0x7
dut.write(0x50, 0x1F)

# glbl_cfg2_sdio_en[0:0] = 0x1
# glbl_cfg2_sdio_mode[1:1] = 0x1
dut.write(0x54, 0x3)

# sysr_cfg3_pulsor_mode[2:0] = 0x1
dut.write(0x5A, 0x1)

# sysr_cfg1_synci_invpol[0:0] = 0x0
# sysr_cfg1_ext_sync_retimemode[2:2] = 0x1
dut.write(0x5B, 0x4)

# sysr_cfg16_divrat_lsb[7:0] = 0x0
dut.write(0x5C, 0x0)

# sysr_cfg16_divrat_msb[3:0] = 0x6
dut.write(0x5D, 0x6)

# dist_cfg1_extvco_islowfreq_sel[0:0] = 0x0
# dist_cfg1_extvco_div2_sel[1:1] = 0x1
dut.write(0x64, 0x2)

# clkgrpx_cfg1_alg_dly_lowpwr_sel[0:0] = 0x0
dut.write(0x65, 0x0)

# alrm_cfg1_sysr_unsyncd_allow[1:1] = 0x0
# alrm_cfg1_clkgrpx_validph_allow[2:2] = 0x0
# alrm_cfg1_sync_req_allow[4:4] = 0x1
dut.write(0x71, 0x10)

# glbl_ro8_chipid_lob[7:0] = 0x1
dut.write(0x78, 0x1)

# glbl_ro8_chipid_mid[7:0] = 0x52
dut.write(0x79, 0x52)

# glbl_ro8_chipid_hib[7:0] = 0x4
dut.write(0x7A, 0x4)

# alrm_ro1_sysr_unsyncd_now[1:1] = 0x1
# alrm_ro1_clkgrpx_validph_now[2:2] = 0x0
# alrm_ro1_sync_req_now[4:4] = 0x1
dut.write(0x7D, 0x12)

# sysr_ro4_fsmstate[3:0] = 0x2
# grpx_ro1_outdivfsm_busy[4:4] = 0x0
dut.write(0x91, 0x2)

# reg_98[7:0] = 0x0
dut.write(0x98, 0x0)

# reg_99[7:0] = 0x0
dut.write(0x99, 0x0)

# reg_9A[7:0] = 0x0
dut.write(0x9A, 0x0)

# reg_9B[7:0] = 0xAA
dut.write(0x9B, 0xAA)

# reg_9C[7:0] = 0xAA
dut.write(0x9C, 0xAA)

# reg_9D[7:0] = 0xAA
dut.write(0x9D, 0xAA)

# reg_9E[7:0] = 0xAA
dut.write(0x9E, 0xAA)

# reg_9F[7:0] = 0x4D
dut.write(0x9F, 0x4D)

# reg_A0[7:0] = 0xDF
dut.write(0xA0, 0xDF)

# reg_A1[7:0] = 0x97
dut.write(0xA1, 0x97)

# reg_A2[7:0] = 0x3
dut.write(0xA2, 0x3)

# reg_A3[7:0] = 0x0
dut.write(0xA3, 0x0)

# reg_A4[7:0] = 0x0
dut.write(0xA4, 0x0)

# reg_AD[7:0] = 0x0
dut.write(0xAD, 0x0)

# reg_AE[7:0] = 0x8
dut.write(0xAE, 0x8)

# reg_AF[7:0] = 0x50
dut.write(0xAF, 0x50)

# reg_B0[7:0] = 0x4
dut.write(0xB0, 0x4)

# reg_B1[7:0] = 0xD
dut.write(0xB1, 0xD)

# reg_B2[7:0] = 0x0
dut.write(0xB2, 0x0)

# reg_B3[7:0] = 0x0
dut.write(0xB3, 0x0)

# reg_B5[7:0] = 0x0
dut.write(0xB5, 0x0)

# reg_B6[7:0] = 0x0
dut.write(0xB6, 0x0)

# reg_B7[7:0] = 0x0
dut.write(0xB7, 0x0)

# reg_B8[7:0] = 0x0
dut.write(0xB8, 0x0)

# clkgrp1_div1_cfg1_en[0:0] = 0x1
# clkgrp1_div1_cfg1_phdelta_mslip[1:1] = 0x1
# clkgrp1_div1_cfg2_startmode[3:2] = 0x0
# clkgrp1_div1_cfg1_rev[4:4] = 0x1
# clkgrp1_div1_cfg1_slipmask[5:5] = 0x1
# clkgrp1_div1_cfg1_reseedmask[6:6] = 0x1
# clkgrp1_div1_cfg1_hi_perf[7:7] = 0x0
dut.write(0xC8, 0x73)

# clkgrp1_div1_cfg12_divrat_lsb[7:0] = 0x1
dut.write(0xC9, 0x1)

# clkgrp1_div1_cfg12_divrat_msb[3:0] = 0x0
dut.write(0xCA, 0x0)

# clkgrp1_div1_cfg5_fine_delay[4:0] = 0x0
dut.write(0xCB, 0x0)

# clkgrp1_div1_cfg5_sel_coarse_delay[4:0] = 0x0
dut.write(0xCC, 0x0)

# clkgrp1_div1_cfg12_mslip_lsb[7:0] = 0x0
dut.write(0xCD, 0x0)

# clkgrp1_div1_cfg12_mslip_msb[3:0] = 0x0
dut.write(0xCE, 0x0)

# clkgrp1_div1_cfg2_sel_outmux[1:0] = 0x3
# clkgrp1_div1_cfg1_drvr_sel_testclk[2:2] = 0x0
dut.write(0xCF, 0x3)

# clkgrp1_div1_cfg5_drvr_res[1:0] = 0x0
# clkgrp1_div1_cfg5_drvr_spare[2:2] = 0x0
# clkgrp1_div1_cfg5_drvr_mode[4:3] = 0x1
# clkgrp1_div1_cfg_outbuf_dyn[5:5] = 0x0
# clkgrp1_div1_cfg2_mutesel[7:6] = 0x0
dut.write(0xD0, 0x8)

# clkgrp1_div2_cfg1_en[0:0] = 0x1
# clkgrp1_div2_cfg1_phdelta_mslip[1:1] = 0x0
# clkgrp1_div2_cfg2_startmode[3:2] = 0x0
# clkgrp1_div2_cfg1_rev[4:4] = 0x1
# clkgrp1_div2_cfg1_slipmask[5:5] = 0x1
# clkgrp1_div2_cfg1_reseedmask[6:6] = 0x1
# clkgrp1_div2_cfg1_hi_perf[7:7] = 0x0
dut.write(0xD2, 0x71)

# clkgrp1_div2_cfg12_divrat_lsb[7:0] = 0x40
dut.write(0xD3, 0x40)

# clkgrp1_div2_cfg12_divrat_msb[3:0] = 0x0
dut.write(0xD4, 0x0)

# clkgrp1_div2_cfg5_fine_delay[4:0] = 0x0
dut.write(0xD5, 0x0)

# clkgrp1_div2_cfg5_sel_coarse_delay[4:0] = 0x0
dut.write(0xD6, 0x0)

# clkgrp1_div2_cfg12_mslip_lsb[7:0] = 0x0
dut.write(0xD7, 0x0)

# clkgrp1_div2_cfg12_mslip_msb[3:0] = 0x0
dut.write(0xD8, 0x0)

# clkgrp1_div2_cfg2_sel_outmux[1:0] = 0x0
# clkgrp1_div2_cfg1_drvr_sel_testclk[2:2] = 0x0
dut.write(0xD9, 0x0)

# clkgrp1_div2_cfg5_drvr_res[1:0] = 0x1
# clkgrp1_div2_cfg5_drvr_spare[2:2] = 0x0
# clkgrp1_div2_cfg5_drvr_mode[4:3] = 0x1
# clkgrp1_div2_cfg_outbuf_dyn[5:5] = 0x0
# clkgrp1_div2_cfg2_mutesel[7:6] = 0x0
dut.write(0xDA, 0x9)

# clkgrp2_div1_cfg1_en[0:0] = 0x1
# clkgrp2_div1_cfg1_phdelta_mslip[1:1] = 0x1
# clkgrp2_div1_cfg2_startmode[3:2] = 0x0
# clkgrp2_div1_cfg1_rev[4:4] = 0x1
# clkgrp2_div1_cfg1_slipmask[5:5] = 0x1
# clkgrp2_div1_cfg1_reseedmask[6:6] = 0x1
# clkgrp2_div1_cfg1_hi_perf[7:7] = 0x0
dut.write(0xDC, 0x73)

# clkgrp2_div1_cfg12_divrat_lsb[7:0] = 0x1
dut.write(0xDD, 0x1)

# clkgrp2_div1_cfg12_divrat_msb[3:0] = 0x0
dut.write(0xDE, 0x0)

# clkgrp2_div1_cfg5_fine_delay[4:0] = 0x0
dut.write(0xDF, 0x0)

# clkgrp2_div1_cfg5_sel_coarse_delay[4:0] = 0x0
dut.write(0xE0, 0x0)

# clkgrp2_div1_cfg12_mslip_lsb[7:0] = 0x0
dut.write(0xE1, 0x0)

# clkgrp2_div1_cfg12_mslip_msb[3:0] = 0x0
dut.write(0xE2, 0x0)

# clkgrp2_div1_cfg2_sel_outmux[1:0] = 0x0
# clkgrp2_div1_cfg1_drvr_sel_testclk[2:2] = 0x0
dut.write(0xE3, 0x0)

# clkgrp2_div1_cfg5_drvr_res[1:0] = 0x0
# clkgrp2_div1_cfg5_drvr_spare[2:2] = 0x0
# clkgrp2_div1_cfg5_drvr_mode[4:3] = 0x1
# clkgrp2_div1_cfg_outbuf_dyn[5:5] = 0x0
# clkgrp2_div1_cfg2_mutesel[7:6] = 0x0
dut.write(0xE4, 0x8)

# clkgrp2_div2_cfg1_en[0:0] = 0x1
# clkgrp2_div2_cfg1_phdelta_mslip[1:1] = 0x0
# clkgrp2_div2_cfg2_startmode[3:2] = 0x0
# clkgrp2_div2_cfg1_rev[4:4] = 0x1
# clkgrp2_div2_cfg1_slipmask[5:5] = 0x1
# clkgrp2_div2_cfg1_reseedmask[6:6] = 0x1
# clkgrp2_div2_cfg1_hi_perf[7:7] = 0x0
dut.write(0xE6, 0x71)

# clkgrp2_div2_cfg12_divrat_lsb[7:0] = 0x40
dut.write(0xE7, 0x40)

# clkgrp2_div2_cfg12_divrat_msb[3:0] = 0x0
dut.write(0xE8, 0x0)

# clkgrp2_div2_cfg5_fine_delay[4:0] = 0x0
dut.write(0xE9, 0x0)

# clkgrp2_div2_cfg5_sel_coarse_delay[4:0] = 0x0
dut.write(0xEA, 0x0)

# clkgrp2_div2_cfg12_mslip_lsb[7:0] = 0x0
dut.write(0xEB, 0x0)

# clkgrp2_div2_cfg12_mslip_msb[3:0] = 0x0
dut.write(0xEC, 0x0)

# clkgrp2_div2_cfg2_sel_outmux[1:0] = 0x0
# clkgrp2_div2_cfg1_drvr_sel_testclk[2:2] = 0x0
dut.write(0xED, 0x0)

# clkgrp2_div2_cfg5_drvr_res[1:0] = 0x1
# clkgrp2_div2_cfg5_drvr_spare[2:2] = 0x0
# clkgrp2_div2_cfg5_drvr_mode[4:3] = 0x1
# clkgrp2_div2_cfg_outbuf_dyn[5:5] = 0x0
# clkgrp2_div2_cfg2_mutesel[7:6] = 0x0
dut.write(0xEE, 0x9)

# clkgrp3_div1_cfg1_en[0:0] = 0x1
# clkgrp3_div1_cfg1_phdelta_mslip[1:1] = 0x1
# clkgrp3_div1_cfg2_startmode[3:2] = 0x0
# clkgrp3_div1_cfg1_rev[4:4] = 0x1
# clkgrp3_div1_cfg1_slipmask[5:5] = 0x1
# clkgrp3_div1_cfg1_reseedmask[6:6] = 0x1
# clkgrp3_div1_cfg1_hi_perf[7:7] = 0x0
dut.write(0xF0, 0x73)

# clkgrp3_div1_cfg12_divrat_lsb[7:0] = 0x2
dut.write(0xF1, 0x2)

# clkgrp3_div1_cfg12_divrat_msb[3:0] = 0x0
dut.write(0xF2, 0x0)

# clkgrp3_div1_cfg5_fine_delay[4:0] = 0x0
dut.write(0xF3, 0x0)

# clkgrp3_div1_cfg5_sel_coarse_delay[4:0] = 0x0
dut.write(0xF4, 0x0)

# clkgrp3_div1_cfg12_mslip_lsb[7:0] = 0x0
dut.write(0xF5, 0x0)

# clkgrp3_div1_cfg12_mslip_msb[3:0] = 0x0
dut.write(0xF6, 0x0)

# clkgrp3_div1_cfg2_sel_outmux[1:0] = 0x0
# clkgrp3_div1_cfg1_drvr_sel_testclk[2:2] = 0x0
dut.write(0xF7, 0x0)

# clkgrp3_div1_cfg5_drvr_res[1:0] = 0x0
# clkgrp3_div1_cfg5_drvr_spare[2:2] = 0x0
# clkgrp3_div1_cfg5_drvr_mode[4:3] = 0x1
# clkgrp3_div1_cfg_outbuf_dyn[5:5] = 0x0
# clkgrp3_div1_cfg2_mutesel[7:6] = 0x0
dut.write(0xF8, 0x8)

# clkgrp3_div2_cfg1_en[0:0] = 0x0
# clkgrp3_div2_cfg1_phdelta_mslip[1:1] = 0x0
# clkgrp3_div2_cfg2_startmode[3:2] = 0x0
# clkgrp3_div2_cfg1_rev[4:4] = 0x1
# clkgrp3_div2_cfg1_slipmask[5:5] = 0x1
# clkgrp3_div2_cfg1_reseedmask[6:6] = 0x1
# clkgrp3_div2_cfg1_hi_perf[7:7] = 0x0
dut.write(0xFA, 0x70)

# clkgrp3_div2_cfg12_divrat_lsb[7:0] = 0x80
dut.write(0xFB, 0x80)

# clkgrp3_div2_cfg12_divrat_msb[3:0] = 0x0
dut.write(0xFC, 0x0)

# clkgrp3_div2_cfg5_fine_delay[4:0] = 0x0
dut.write(0xFD, 0x0)

# clkgrp3_div2_cfg5_sel_coarse_delay[4:0] = 0x0
dut.write(0xFE, 0x0)

# clkgrp3_div2_cfg12_mslip_lsb[7:0] = 0x0
dut.write(0xFF, 0x0)

# clkgrp3_div2_cfg12_mslip_msb[3:0] = 0x0
dut.write(0x100, 0x0)

# clkgrp3_div2_cfg2_sel_outmux[1:0] = 0x0
# clkgrp3_div2_cfg1_drvr_sel_testclk[2:2] = 0x0
dut.write(0x101, 0x0)

# clkgrp3_div2_cfg5_drvr_res[1:0] = 0x3
# clkgrp3_div2_cfg5_drvr_spare[2:2] = 0x0
# clkgrp3_div2_cfg5_drvr_mode[4:3] = 0x1
# clkgrp3_div2_cfg_outbuf_dyn[5:5] = 0x0
# clkgrp3_div2_cfg2_mutesel[7:6] = 0x0
dut.write(0x102, 0xB)

# clkgrp4_div1_cfg1_en[0:0] = 0x1
# clkgrp4_div1_cfg1_phdelta_mslip[1:1] = 0x1
# clkgrp4_div1_cfg2_startmode[3:2] = 0x0
# clkgrp4_div1_cfg1_rev[4:4] = 0x1
# clkgrp4_div1_cfg1_slipmask[5:5] = 0x1
# clkgrp4_div1_cfg1_reseedmask[6:6] = 0x1
# clkgrp4_div1_cfg1_hi_perf[7:7] = 0x0
dut.write(0x104, 0x73)

# clkgrp4_div1_cfg12_divrat_lsb[7:0] = 0x4
dut.write(0x105, 0x4)

# clkgrp4_div1_cfg12_divrat_msb[3:0] = 0x0
dut.write(0x106, 0x0)

# clkgrp4_div1_cfg5_fine_delay[4:0] = 0x0
dut.write(0x107, 0x0)

# clkgrp4_div1_cfg5_sel_coarse_delay[4:0] = 0x0
dut.write(0x108, 0x0)

# clkgrp4_div1_cfg12_mslip_lsb[7:0] = 0x0
dut.write(0x109, 0x0)

# clkgrp4_div1_cfg12_mslip_msb[3:0] = 0x0
dut.write(0x10A, 0x0)

# clkgrp4_div1_cfg2_sel_outmux[1:0] = 0x0
# clkgrp4_div1_cfg1_drvr_sel_testclk[2:2] = 0x0
dut.write(0x10B, 0x0)

# clkgrp4_div1_cfg5_drvr_res[1:0] = 0x0
# clkgrp4_div1_cfg5_drvr_spare[2:2] = 0x0
# clkgrp4_div1_cfg5_drvr_mode[4:3] = 0x1
# clkgrp4_div1_cfg_outbuf_dyn[5:5] = 0x0
# clkgrp4_div1_cfg2_mutesel[7:6] = 0x0
dut.write(0x10C, 0x8)

# clkgrp4_div2_cfg1_en[0:0] = 0x1
# clkgrp4_div2_cfg1_phdelta_mslip[1:1] = 0x0
# clkgrp4_div2_cfg2_startmode[3:2] = 0x0
# clkgrp4_div2_cfg1_rev[4:4] = 0x1
# clkgrp4_div2_cfg1_slipmask[5:5] = 0x1
# clkgrp4_div2_cfg1_reseedmask[6:6] = 0x1
# clkgrp4_div2_cfg1_hi_perf[7:7] = 0x0
dut.write(0x10E, 0x71)

# clkgrp4_div2_cfg12_divrat_lsb[7:0] = 0x40
dut.write(0x10F, 0x40)

# clkgrp4_div2_cfg12_divrat_msb[3:0] = 0x0
dut.write(0x110, 0x0)

# clkgrp4_div2_cfg5_fine_delay[4:0] = 0x0
dut.write(0x111, 0x0)

# clkgrp4_div2_cfg5_sel_coarse_delay[4:0] = 0x0
dut.write(0x112, 0x0)

# clkgrp4_div2_cfg12_mslip_lsb[7:0] = 0x0
dut.write(0x113, 0x0)

# clkgrp4_div2_cfg12_mslip_msb[3:0] = 0x0
dut.write(0x114, 0x0)

# clkgrp4_div2_cfg2_sel_outmux[1:0] = 0x0
# clkgrp4_div2_cfg1_drvr_sel_testclk[2:2] = 0x0
dut.write(0x115, 0x0)

# clkgrp4_div2_cfg5_drvr_res[1:0] = 0x3
# clkgrp4_div2_cfg5_drvr_spare[2:2] = 0x0
# clkgrp4_div2_cfg5_drvr_mode[4:3] = 0x2
# clkgrp4_div2_cfg_outbuf_dyn[5:5] = 0x0
# clkgrp4_div2_cfg2_mutesel[7:6] = 0x0
dut.write(0x116, 0x13)

# clkgrp5_div1_cfg1_en[0:0] = 0x1
# clkgrp5_div1_cfg1_phdelta_mslip[1:1] = 0x1
# clkgrp5_div1_cfg2_startmode[3:2] = 0x0
# clkgrp5_div1_cfg1_rev[4:4] = 0x1
# clkgrp5_div1_cfg1_slipmask[5:5] = 0x1
# clkgrp5_div1_cfg1_reseedmask[6:6] = 0x1
# clkgrp5_div1_cfg1_hi_perf[7:7] = 0x0
dut.write(0x118, 0x73)

# clkgrp5_div1_cfg12_divrat_lsb[7:0] = 0x4
dut.write(0x119, 0x4)

# clkgrp5_div1_cfg12_divrat_msb[3:0] = 0x0
dut.write(0x11A, 0x0)

# clkgrp5_div1_cfg5_fine_delay[4:0] = 0x0
dut.write(0x11B, 0x0)

# clkgrp5_div1_cfg5_sel_coarse_delay[4:0] = 0x0
dut.write(0x11C, 0x0)

# clkgrp5_div1_cfg12_mslip_lsb[7:0] = 0x0
dut.write(0x11D, 0x0)

# clkgrp5_div1_cfg12_mslip_msb[3:0] = 0x0
dut.write(0x11E, 0x0)

# clkgrp5_div1_cfg2_sel_outmux[1:0] = 0x0
# clkgrp5_div1_cfg1_drvr_sel_testclk[2:2] = 0x0
dut.write(0x11F, 0x0)

# clkgrp5_div1_cfg5_drvr_res[1:0] = 0x0
# clkgrp5_div1_cfg5_drvr_spare[2:2] = 0x0
# clkgrp5_div1_cfg5_drvr_mode[4:3] = 0x1
# clkgrp5_div1_cfg_outbuf_dyn[5:5] = 0x0
# clkgrp5_div1_cfg2_mutesel[7:6] = 0x0
dut.write(0x120, 0x8)

# clkgrp5_div2_cfg1_en[0:0] = 0x1
# clkgrp5_div2_cfg1_phdelta_mslip[1:1] = 0x1
# clkgrp5_div2_cfg2_startmode[3:2] = 0x0
# clkgrp5_div2_cfg1_rev[4:4] = 0x1
# clkgrp5_div2_cfg1_slipmask[5:5] = 0x1
# clkgrp5_div2_cfg1_reseedmask[6:6] = 0x1
# clkgrp5_div2_cfg1_hi_perf[7:7] = 0x0
dut.write(0x122, 0x73)

# clkgrp5_div2_cfg12_divrat_lsb[7:0] = 0x4
dut.write(0x123, 0x4)

# clkgrp5_div2_cfg12_divrat_msb[3:0] = 0x0
dut.write(0x124, 0x0)

# clkgrp5_div2_cfg5_fine_delay[4:0] = 0x0
dut.write(0x125, 0x0)

# clkgrp5_div2_cfg5_sel_coarse_delay[4:0] = 0x0
dut.write(0x126, 0x0)

# clkgrp5_div2_cfg12_mslip_lsb[7:0] = 0x0
dut.write(0x127, 0x0)

# clkgrp5_div2_cfg12_mslip_msb[3:0] = 0x0
dut.write(0x128, 0x0)

# clkgrp5_div2_cfg2_sel_outmux[1:0] = 0x0
# clkgrp5_div2_cfg1_drvr_sel_testclk[2:2] = 0x0
dut.write(0x129, 0x0)

# clkgrp5_div2_cfg5_drvr_res[1:0] = 0x3
# clkgrp5_div2_cfg5_drvr_spare[2:2] = 0x0
# clkgrp5_div2_cfg5_drvr_mode[4:3] = 0x1
# clkgrp5_div2_cfg_outbuf_dyn[5:5] = 0x0
# clkgrp5_div2_cfg2_mutesel[7:6] = 0x0
dut.write(0x12A, 0xB)

# clkgrp6_div1_cfg1_en[0:0] = 0x1
# clkgrp6_div1_cfg1_phdelta_mslip[1:1] = 0x1
# clkgrp6_div1_cfg2_startmode[3:2] = 0x0
# clkgrp6_div1_cfg1_rev[4:4] = 0x1
# clkgrp6_div1_cfg1_slipmask[5:5] = 0x1
# clkgrp6_div1_cfg1_reseedmask[6:6] = 0x1
# clkgrp6_div1_cfg1_hi_perf[7:7] = 0x0
dut.write(0x12C, 0x73)

# clkgrp6_div1_cfg12_divrat_lsb[7:0] = 0x4
dut.write(0x12D, 0x4)

# clkgrp6_div1_cfg12_divrat_msb[3:0] = 0x0
dut.write(0x12E, 0x0)

# clkgrp6_div1_cfg5_fine_delay[4:0] = 0x0
dut.write(0x12F, 0x0)

# clkgrp6_div1_cfg5_sel_coarse_delay[4:0] = 0x0
dut.write(0x130, 0x0)

# clkgrp6_div1_cfg12_mslip_lsb[7:0] = 0x0
dut.write(0x131, 0x0)

# clkgrp6_div1_cfg12_mslip_msb[3:0] = 0x0
dut.write(0x132, 0x0)

# clkgrp6_div1_cfg2_sel_outmux[1:0] = 0x0
# clkgrp6_div1_cfg1_drvr_sel_testclk[2:2] = 0x0
dut.write(0x133, 0x0)

# clkgrp6_div1_cfg5_drvr_res[1:0] = 0x0
# clkgrp6_div1_cfg5_drvr_spare[2:2] = 0x0
# clkgrp6_div1_cfg5_drvr_mode[4:3] = 0x1
# clkgrp6_div1_cfg_outbuf_dyn[5:5] = 0x0
# clkgrp6_div1_cfg2_mutesel[7:6] = 0x0
dut.write(0x134, 0x8)

# clkgrp6_div2_cfg1_en[0:0] = 0x1
# clkgrp6_div2_cfg1_phdelta_mslip[1:1] = 0x0
# clkgrp6_div2_cfg2_startmode[3:2] = 0x0
# clkgrp6_div2_cfg1_rev[4:4] = 0x1
# clkgrp6_div2_cfg1_slipmask[5:5] = 0x1
# clkgrp6_div2_cfg1_reseedmask[6:6] = 0x1
# clkgrp6_div2_cfg1_hi_perf[7:7] = 0x0
dut.write(0x136, 0x71)

# clkgrp6_div2_cfg12_divrat_lsb[7:0] = 0x80
dut.write(0x137, 0x80)

# clkgrp6_div2_cfg12_divrat_msb[3:0] = 0x0
dut.write(0x138, 0x0)

# clkgrp6_div2_cfg5_fine_delay[4:0] = 0x0
dut.write(0x139, 0x0)

# clkgrp6_div2_cfg5_sel_coarse_delay[4:0] = 0x0
dut.write(0x13A, 0x0)

# clkgrp6_div2_cfg12_mslip_lsb[7:0] = 0x0
dut.write(0x13B, 0x0)

# clkgrp6_div2_cfg12_mslip_msb[3:0] = 0x0
dut.write(0x13C, 0x0)

# clkgrp6_div2_cfg2_sel_outmux[1:0] = 0x0
# clkgrp6_div2_cfg1_drvr_sel_testclk[2:2] = 0x0
dut.write(0x13D, 0x0)

# clkgrp6_div2_cfg5_drvr_res[1:0] = 0x1
# clkgrp6_div2_cfg5_drvr_spare[2:2] = 0x0
# clkgrp6_div2_cfg5_drvr_mode[4:3] = 0x2
# clkgrp6_div2_cfg_outbuf_dyn[5:5] = 0x0
# clkgrp6_div2_cfg2_mutesel[7:6] = 0x0
dut.write(0x13E, 0x11)

# clkgrp7_div1_cfg1_en[0:0] = 0x0
# clkgrp7_div1_cfg1_phdelta_mslip[1:1] = 0x1
# clkgrp7_div1_cfg2_startmode[3:2] = 0x0
# clkgrp7_div1_cfg1_rev[4:4] = 0x1
# clkgrp7_div1_cfg1_slipmask[5:5] = 0x1
# clkgrp7_div1_cfg1_reseedmask[6:6] = 0x1
# clkgrp7_div1_cfg1_hi_perf[7:7] = 0x0
dut.write(0x140, 0x72)

# clkgrp7_div1_cfg12_divrat_lsb[7:0] = 0x2
dut.write(0x141, 0x2)

# clkgrp7_div1_cfg12_divrat_msb[3:0] = 0x0
dut.write(0x142, 0x0)

# clkgrp7_div1_cfg5_fine_delay[4:0] = 0x0
dut.write(0x143, 0x0)

# clkgrp7_div1_cfg5_sel_coarse_delay[4:0] = 0x0
dut.write(0x144, 0x0)

# clkgrp7_div1_cfg12_mslip_lsb[7:0] = 0x0
dut.write(0x145, 0x0)

# clkgrp7_div1_cfg12_mslip_msb[3:0] = 0x0
dut.write(0x146, 0x0)

# clkgrp7_div1_cfg2_sel_outmux[1:0] = 0x0
# clkgrp7_div1_cfg1_drvr_sel_testclk[2:2] = 0x0
dut.write(0x147, 0x0)

# clkgrp7_div1_cfg5_drvr_res[1:0] = 0x0
# clkgrp7_div1_cfg5_drvr_spare[2:2] = 0x0
# clkgrp7_div1_cfg5_drvr_mode[4:3] = 0x1
# clkgrp7_div1_cfg_outbuf_dyn[5:5] = 0x0
# clkgrp7_div1_cfg2_mutesel[7:6] = 0x0
dut.write(0x148, 0x8)

# clkgrp7_div2_cfg1_en[0:0] = 0x0
# clkgrp7_div2_cfg1_phdelta_mslip[1:1] = 0x0
# clkgrp7_div2_cfg2_startmode[3:2] = 0x0
# clkgrp7_div2_cfg1_rev[4:4] = 0x1
# clkgrp7_div2_cfg1_slipmask[5:5] = 0x1
# clkgrp7_div2_cfg1_reseedmask[6:6] = 0x1
# clkgrp7_div2_cfg1_hi_perf[7:7] = 0x0
dut.write(0x14A, 0x70)

# clkgrp7_div2_cfg12_divrat_lsb[7:0] = 0x80
dut.write(0x14B, 0x80)

# clkgrp7_div2_cfg12_divrat_msb[3:0] = 0x0
dut.write(0x14C, 0x0)

# clkgrp7_div2_cfg5_fine_delay[4:0] = 0x0
dut.write(0x14D, 0x0)

# clkgrp7_div2_cfg5_sel_coarse_delay[4:0] = 0x0
dut.write(0x14E, 0x0)

# clkgrp7_div2_cfg12_mslip_lsb[7:0] = 0x0
dut.write(0x14F, 0x0)

# clkgrp7_div2_cfg12_mslip_msb[3:0] = 0x0
dut.write(0x150, 0x0)

# clkgrp7_div2_cfg2_sel_outmux[1:0] = 0x0
# clkgrp7_div2_cfg1_drvr_sel_testclk[2:2] = 0x0
dut.write(0x151, 0x0)

# clkgrp7_div2_cfg5_drvr_res[1:0] = 0x3
# clkgrp7_div2_cfg5_drvr_spare[2:2] = 0x0
# clkgrp7_div2_cfg5_drvr_mode[4:3] = 0x1
# clkgrp7_div2_cfg_outbuf_dyn[5:5] = 0x0
# clkgrp7_div2_cfg2_mutesel[7:6] = 0x0
dut.write(0x152, 0xB)