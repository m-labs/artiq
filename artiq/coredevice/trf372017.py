class TRF372017:
    """TRF372017 settings and register map.

    For possible values, documentation, and explanation, see the datasheet.
    https://www.ti.com/lit/gpn/trf372017
    """
    rdiv = 2  # 13b - highest valid f_PFD
    ref_inv = 0
    neg_vco = 1
    icp = 0  # 1.94 mA, 5b
    icp_double = 0
    cal_clk_sel = 0b1110  # div64, 4b

    # default f_vco is 2.875 GHz
    nint = 23  # 16b - lowest value suitable for fractional & integer mode
    pll_div_sel = 0b01  # div2, 2b
    prsc_sel = 0  # 4/5
    vco_sel = 2  # 2b
    vcosel_mode = 0
    cal_acc = 0b00  # 2b
    en_cal = 0  # leave at 0 - calibration is performed in `Phaser.init()`

    nfrac = 0  # 25b

    pwd_pll = 0
    pwd_cp = 0
    pwd_vco = 0
    pwd_vcomux = 0
    pwd_div124 = 0
    pwd_presc = 0
    pwd_out_buff = 1  # leave at 1 - only enable outputs after calibration
    pwd_lo_div = 1  # leave at 1 - only enable outputs after calibration
    pwd_tx_div = 1  # leave at 1 - only enable outputs after calibration
    pwd_bb_vcm = 0
    pwd_dc_off = 0
    en_extvco = 0
    en_isource = 0
    ld_ana_prec = 0  # 2b
    cp_tristate = 0  # 2b
    speedup = 0
    ld_dig_prec = 1
    en_dith = 1
    mod_ord = 2  # 3rd order, 2b
    dith_sel = 0
    del_sd_clk = 2  # 2b
    en_frac = 0

    vcobias_rtrim = 4  # 3b
    pllbias_rtrim = 2  # 2b
    vco_bias = 8  # 460 µA, 4b
    vcobuf_bias = 2  # 2b
    vcomux_bias = 3  # 2b
    bufout_bias = 0  # 300 µA, 2b
    vco_cal_ib = 0  # PTAT
    vco_cal_ref = 2  # 1.04 V, 2b
    vco_ampl_ctrl = 3  # 2b
    vco_vb_ctrl = 0  # 1.2 V, 2b
    en_ld_isource = 0

    ioff = 0x80  # 8b
    qoff = 0x80  # 8b
    vref_sel = 4  # 0.85 V, 3b
    tx_div_sel = 0  # div1, 2b
    lo_div_sel = 0  # div1, 2b
    tx_div_bias = 1  # 37.5 µA, 2b
    lo_div_bias = 2  # 50 µA, 2b

    vco_trim = 0x20  # 6b
    vco_test_mode = 0
    cal_bypass = 0
    mux_ctrl = 1  # lock detect, 3b
    isource_sink = 0
    isource_trim = 4  # 3b
    pd_tc = 0  # 2b
    ib_vcm_sel = 0  # ptat
    dcoffset_i = 2  # 150 µA, 2b
    vco_bias_sel = 1  # spi

    def __init__(self, updates=None):
        if updates is None:
            return
        for key, value in updates.items():
            if not hasattr(self, key):
                raise KeyError("invalid setting", key)
            setattr(self, key, value)

    def get_mmap(self):
        """Memory map for TRF372017"""
        mmap = []
        mmap.append(
            0x9 |
            (self.rdiv << 5) | (self.ref_inv << 19) | (self.neg_vco << 20) |
            (self.icp << 21) | (self.icp_double << 26) |
            (self.cal_clk_sel << 27))
        mmap.append(
            0xa |
            (self.nint << 5) | (self.pll_div_sel << 21) |
            (self.prsc_sel << 23) | (self.vco_sel << 26) |
            (self.vcosel_mode << 28) | (self.cal_acc << 29) |
            (self.en_cal << 31))
        mmap.append(0xb | (self.nfrac << 5))
        mmap.append(
            0xc |
            (self.pwd_pll << 5) | (self.pwd_cp << 6) | (self.pwd_vco << 7) |
            (self.pwd_vcomux << 8) | (self.pwd_div124 << 9) |
            (self.pwd_presc << 10) | (self.pwd_out_buff << 12) |
            (self.pwd_lo_div << 13) | (self.pwd_tx_div << 14) |
            (self.pwd_bb_vcm << 15) | (self.pwd_dc_off << 16) |
            (self.en_extvco << 17) | (self.en_isource << 18) |
            (self.ld_ana_prec << 19) | (self.cp_tristate << 21) |
            (self.speedup << 23) | (self.ld_dig_prec << 24) |
            (self.en_dith << 25) | (self.mod_ord << 26) |
            (self.dith_sel << 28) | (self.del_sd_clk << 29) |
            (self.en_frac << 31))
        mmap.append(
            0xd |
            (self.vcobias_rtrim << 5) | (self.pllbias_rtrim << 8) |
            (self.vco_bias << 10) | (self.vcobuf_bias << 14) |
            (self.vcomux_bias << 16) | (self.bufout_bias << 18) |
            (1 << 21) | (self.vco_cal_ib << 22) | (self.vco_cal_ref << 23) |
            (self.vco_ampl_ctrl << 26) | (self.vco_vb_ctrl << 28) |
            (self.en_ld_isource << 31))
        mmap.append(
            0xe |
            (self.ioff << 5) | (self.qoff << 13) | (self.vref_sel << 21) |
            (self.tx_div_sel << 24) | (self.lo_div_sel << 26) |
            (self.tx_div_bias << 28) | (self.lo_div_bias << 30))
        mmap.append(
            0xf |
            (self.vco_trim << 7) | (self.vco_test_mode << 14) |
            (self.cal_bypass << 15) | (self.mux_ctrl << 16) |
            (self.isource_sink << 19) | (self.isource_trim << 20) |
            (self.pd_tc << 23) | (self.ib_vcm_sel << 25) |
            (1 << 28) | (self.dcoffset_i << 29) |
            (self.vco_bias_sel << 31))
        return mmap
