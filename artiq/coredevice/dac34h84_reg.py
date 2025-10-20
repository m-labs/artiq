class DAC34H84:
    """DAC34H84 settings and register map.

    For possible values, documentation, and explanation, see the DAC datasheet
    at https://www.ti.com/lit/pdf/slas751
    """
    qmc_corr_ena = 0  # msb ab
    qmc_offset_ena = 0  # msb ab
    invsinc_ena = 0  # msb ab
    interpolation = 1  # 2x
    fifo_ena = 1
    alarm_out_ena = 1
    alarm_out_pol = 1
    clkdiv_sync_ena = 1

    iotest_ena = 0
    cnt64_ena = 0
    oddeven_parity = 0  # even
    single_parity_ena = 1
    dual_parity_ena = 0
    rev_interface = 0
    dac_complement = 0b0000  # msb A
    alarm_fifo = 0b111  # msb 2-away

    dacclkgone_ena = 1
    dataclkgone_ena = 1
    collisiongone_ena = 1
    sif4_ena = 1
    mixer_ena = 0
    mixer_gain = 1
    nco_ena = 0
    revbus = 0
    twos = 1

    coarse_dac = 9  # 18.75 mA, 0-15
    sif_txenable = 0

    mask_alarm_from_zerochk = 0
    mask_alarm_fifo_collision = 0
    mask_alarm_fifo_1away = 0
    mask_alarm_fifo_2away = 0
    mask_alarm_dacclk_gone = 0
    mask_alarm_dataclk_gone = 0
    mask_alarm_output_gone = 0
    mask_alarm_from_iotest = 0
    mask_alarm_from_pll = 0
    mask_alarm_parity = 0b0000  # msb a

    qmc_offseta = 0  # 12b
    fifo_offset = 2  # 0-7
    qmc_offsetb = 0  # 12b

    qmc_offsetc = 0  # 12b

    qmc_offsetd = 0  # 12b

    qmc_gaina = 0  # 11b

    cmix_fs8 = 0
    cmix_fs4 = 0
    cmix_fs2 = 0
    cmix_nfs4 = 0
    qmc_gainb = 0  # 11b

    qmc_gainc = 0  # 11b

    output_delayab = 0b00
    output_delaycd = 0b00
    qmc_gaind = 0  # 11b

    qmc_phaseab = 0  # 12b

    qmc_phasecd = 0  # 12b

    phase_offsetab = 0  # 16b
    phase_offsetcd = 0  # 16b
    phase_addab_lsb = 0  # 16b
    phase_addab_msb = 0  # 16b
    phase_addcd_lsb = 0  # 16b
    phase_addcd_msb = 0  # 16b

    pll_reset = 0
    pll_ndivsync_ena = 1
    pll_ena = 1
    pll_cp = 0b01  # single charge pump
    pll_p = 0b100  # p=4

    pll_m2 = 1  # x2
    pll_m = 8  # m = 8
    pll_n = 0b0001  # n = 2
    pll_vcotune = 0b01

    pll_vco = 0x3f  # 4 GHz
    bias_sleep = 0
    tsense_sleep = 0
    pll_sleep = 0
    clkrecv_sleep = 0
    dac_sleep = 0b0000  # msb a

    extref_ena = 0
    fuse_sleep = 1
    atest = 0b00000  # atest mode

    syncsel_qmcoffsetab = 0b1001  # sif_sync and register write
    syncsel_qmcoffsetcd = 0b1001  # sif_sync and register write
    syncsel_qmccorrab = 0b1001  # sif_sync and register write
    syncsel_qmccorrcd = 0b1001  # sif_sync and register write

    syncsel_mixerab = 0b1001  # sif_sync and register write
    syncsel_mixercd = 0b1001  # sif_sync and register write
    syncsel_nco = 0b1000  # sif_sync
    syncsel_fifo_input = 0b10  # external lvds istr
    sif_sync = 0

    syncsel_fifoin = 0b0010  # istr
    syncsel_fifoout = 0b0100  # ostr
    clkdiv_sync_sel = 0  # ostr

    path_a_sel = 0
    path_b_sel = 1
    path_c_sel = 2
    path_d_sel = 3
    # swap dac pairs (CDAB) for layout
    # swap I-Q dacs for spectral inversion
    dac_a_sel = 3
    dac_b_sel = 2
    dac_c_sel = 1
    dac_d_sel = 0

    dac_sleep_en = 0b1111  # msb a
    clkrecv_sleep_en = 1
    pll_sleep_en = 1
    lvds_data_sleep_en = 1
    lvds_control_sleep_en = 1
    temp_sense_sleep_en = 1
    bias_sleep_en = 1

    data_dly = 2
    clk_dly = 0

    ostrtodig_sel = 0
    ramp_ena = 0
    sifdac_ena = 0

    grp_delaya = 0x00
    grp_delayb = 0x00

    grp_delayc = 0x00
    grp_delayd = 0x00

    sifdac = 0

    def __init__(self, updates=None):
        if updates is None:
            return
        for key, value in updates.items():
            if not hasattr(self, key):
                raise KeyError("invalid setting", key)
            setattr(self, key, value)

    def get_mmap(self):
        mmap = []
        mmap.append(
            (0x00 << 16) |
            (self.qmc_offset_ena << 14) | (self.qmc_corr_ena << 12) |
            (self.interpolation << 8) | (self.fifo_ena << 7) |
            (self.alarm_out_ena << 4) | (self.alarm_out_pol << 3) |
            (self.clkdiv_sync_ena << 2) | (self.invsinc_ena << 0))
        mmap.append(
            (0x01 << 16) |
            (self.iotest_ena << 15) | (self.cnt64_ena << 12) |
            (self.oddeven_parity << 11) | (self.single_parity_ena << 10) |
            (self.dual_parity_ena << 9) | (self.rev_interface << 8) |
            (self.dac_complement << 4) | (self.alarm_fifo << 1))
        mmap.append(
            (0x02 << 16) |
            (self.dacclkgone_ena << 14) | (self.dataclkgone_ena << 13) |
            (self.collisiongone_ena << 12) | (self.sif4_ena << 7) |
            (self.mixer_ena << 6) | (self.mixer_gain << 5) |
            (self.nco_ena << 4) | (self.revbus << 3) | (self.twos << 1))
        mmap.append((0x03 << 16) | (self.coarse_dac << 12) |
                    (self.sif_txenable << 0))
        mmap.append(
            (0x07 << 16) |
            (self.mask_alarm_from_zerochk << 15) | (1 << 14) |
            (self.mask_alarm_fifo_collision << 13) |
            (self.mask_alarm_fifo_1away << 12) |
            (self.mask_alarm_fifo_2away << 11) |
            (self.mask_alarm_dacclk_gone << 10) |
            (self.mask_alarm_dataclk_gone << 9) |
            (self.mask_alarm_output_gone << 8) |
            (self.mask_alarm_from_iotest << 7) | (1 << 6) |
            (self.mask_alarm_from_pll << 5) | (self.mask_alarm_parity << 1))
        mmap.append(
            (0x08 << 16) | (self.qmc_offseta << 0))
        mmap.append(
            (0x09 << 16) | (self.fifo_offset << 13) | (self.qmc_offsetb << 0))
        mmap.append((0x0a << 16) | (self.qmc_offsetc << 0))
        mmap.append((0x0b << 16) | (self.qmc_offsetd << 0))
        mmap.append((0x0c << 16) | (self.qmc_gaina << 0))
        mmap.append(
            (0x0d << 16) |
            (self.cmix_fs8 << 15) | (self.cmix_fs4 << 14) |
            (self.cmix_fs2 << 13) | (self.cmix_nfs4 << 12) |
            (self.qmc_gainb << 0))
        mmap.append((0x0e << 16) | (self.qmc_gainc << 0))
        mmap.append(
            (0x0f << 16) |
            (self.output_delayab << 14) | (self.output_delaycd << 12) |
            (self.qmc_gaind << 0))
        mmap.append((0x10 << 16) | (self.qmc_phaseab << 0))
        mmap.append((0x11 << 16) | (self.qmc_phasecd << 0))
        mmap.append((0x12 << 16) | (self.phase_offsetab << 0))
        mmap.append((0x13 << 16) | (self.phase_offsetcd << 0))
        mmap.append((0x14 << 16) | (self.phase_addab_lsb << 0))
        mmap.append((0x15 << 16) | (self.phase_addab_msb << 0))
        mmap.append((0x16 << 16) | (self.phase_addcd_lsb << 0))
        mmap.append((0x17 << 16) | (self.phase_addcd_msb << 0))
        mmap.append(
            (0x18 << 16) |
            (0b001 << 13) | (self.pll_reset << 12) |
            (self.pll_ndivsync_ena << 11) | (self.pll_ena << 10) |
            (self.pll_cp << 6) | (self.pll_p << 3))
        mmap.append(
            (0x19 << 16) |
            (self.pll_m2 << 15) | (self.pll_m << 8) | (self.pll_n << 4) |
            (self.pll_vcotune << 2))
        mmap.append(
            (0x1a << 16) |
            (self.pll_vco << 10) | (self.bias_sleep << 7) |
            (self.tsense_sleep << 6) |
            (self.pll_sleep << 5) | (self.clkrecv_sleep << 4) |
            (self.dac_sleep << 0))
        mmap.append(
            (0x1b << 16) |
            (self.extref_ena << 15) | (self.fuse_sleep << 11) |
            (self.atest << 0))
        mmap.append(
            (0x1e << 16) |
            (self.syncsel_qmcoffsetab << 12) |
            (self.syncsel_qmcoffsetcd << 8) |
            (self.syncsel_qmccorrab << 4) |
            (self.syncsel_qmccorrcd << 0))
        mmap.append(
            (0x1f << 16) |
            (self.syncsel_mixerab << 12) | (self.syncsel_mixercd << 8) |
            (self.syncsel_nco << 4) | (self.syncsel_fifo_input << 2) |
            (self.sif_sync << 1))
        mmap.append(
            (0x20 << 16) |
            (self.syncsel_fifoin << 12) | (self.syncsel_fifoout << 8) |
            (self.clkdiv_sync_sel << 0))
        mmap.append(
            (0x22 << 16) |
            (self.path_a_sel << 14) | (self.path_b_sel << 12) |
            (self.path_c_sel << 10) | (self.path_d_sel << 8) |
            (self.dac_a_sel << 6) | (self.dac_b_sel << 4) |
            (self.dac_c_sel << 2) | (self.dac_d_sel << 0))
        mmap.append(
            (0x23 << 16) |
            (self.dac_sleep_en << 12) | (self.clkrecv_sleep_en << 11) |
            (self.pll_sleep_en << 10) | (self.lvds_data_sleep_en << 9) |
            (self.lvds_control_sleep_en << 8) |
            (self.temp_sense_sleep_en << 7) | (1 << 6) |
            (self.bias_sleep_en << 5) | (0x1f << 0))
        mmap.append(
            (0x24 << 16) | (self.data_dly << 13) | (self.clk_dly << 10))
        mmap.append(
            (0x2d << 16) |
            (self.ostrtodig_sel << 14) | (self.ramp_ena << 13) |
            (0x002 << 1) | (self.sifdac_ena << 0))
        mmap.append(
            (0x2e << 16) | (self.grp_delaya << 8) | (self.grp_delayb << 0))
        mmap.append(
            (0x2f << 16) | (self.grp_delayc << 8) | (self.grp_delayd << 0))
        mmap.append((0x30 << 16) | self.sifdac)
        return mmap
