#include <generated/csr.h>
#include <stdio.h>

#include "artiq_personality.h"
#include "rtio.h"
#include "log.h"
#include "dds.h"

#define DURATION_WRITE (5 << CONFIG_RTIO_FINE_TS_WIDTH)

#if defined CONFIG_DDS_AD9858
/* Assume 8-bit bus */
#define DURATION_INIT (7*DURATION_WRITE) /* not counting FUD */
#define DURATION_PROGRAM (8*DURATION_WRITE) /* not counting FUD */

#elif defined CONFIG_DDS_AD9914
/* Assume 16-bit bus */
/* DAC calibration takes max. 1ms as per datasheet */
#define DURATION_DAC_CAL (147000 << CONFIG_RTIO_FINE_TS_WIDTH)
/* not counting final FUD */
#define DURATION_INIT (8*DURATION_WRITE + DURATION_DAC_CAL)
#define DURATION_PROGRAM (6*DURATION_WRITE) /* not counting FUD */

#else
#error Unknown DDS configuration
#endif

#define DDS_WRITE(addr, data) do { \
        rtio_output(now, bus_channel, addr, data); \
        now += DURATION_WRITE; \
    } while(0)

void dds_init(long long int timestamp, int bus_channel, int channel)
{
    long long int now;

    now = timestamp - DURATION_INIT;

#ifdef CONFIG_DDS_ONEHOT_SEL
    channel = 1 << channel;
#endif
    channel <<= 1;
    DDS_WRITE(DDS_GPIO, channel);
#ifndef CONFIG_DDS_AD9914
    /*
     * Resetting a AD9914 intermittently crashes it. It does not produce any
     * output until power-cycled.
     * Increasing the reset pulse length and the delay until the first write
     * to 300ns do not solve the problem.
     * The chips seem fine without a reset.
     */
    DDS_WRITE(DDS_GPIO, channel | 1); /* reset */
    DDS_WRITE(DDS_GPIO, channel);
#endif

#ifdef CONFIG_DDS_AD9858
    /*
     * 2GHz divider disable
     * SYNCLK disable
     * Mixer power-down
     * Phase detect power down
     */
    DDS_WRITE(DDS_CFR0, 0x78);
    DDS_WRITE(DDS_CFR1, 0x00);
    DDS_WRITE(DDS_CFR2, 0x00);
    DDS_WRITE(DDS_CFR3, 0x00);
    DDS_WRITE(DDS_FUD, 0);
#endif

#ifdef CONFIG_DDS_AD9914
    DDS_WRITE(DDS_CFR1H, 0x0000); /* Enable cosine output */
    DDS_WRITE(DDS_CFR2L, 0x8900); /* Enable matched latency */
    DDS_WRITE(DDS_CFR2H, 0x0080); /* Enable profile mode */
    DDS_WRITE(DDS_ASF, 0x0fff); /* Set amplitude to maximum */
    DDS_WRITE(DDS_CFR4H, 0x0105); /* Enable DAC calibration */
    DDS_WRITE(DDS_FUD, 0);
    now += DURATION_DAC_CAL;
    DDS_WRITE(DDS_CFR4H, 0x0005); /* Disable DAC calibration */
    DDS_WRITE(DDS_FUD, 0);
#endif
}

/* Compensation to keep phase continuity when switching from absolute or tracking
 * to continuous phase mode. */
static unsigned int continuous_phase_comp[CONFIG_RTIO_DDS_COUNT][CONFIG_DDS_CHANNELS_PER_BUS];

static void dds_set_one(long long int now, long long int ref_time,
    int bus_channel, int channel,
    unsigned int ftw, unsigned int pow, int phase_mode, unsigned int amplitude)
{
    unsigned int channel_enc;

    if((channel < 0) || (channel >= CONFIG_DDS_CHANNELS_PER_BUS)) {
        core_log("Attempted to set invalid DDS channel\n");
        return;
    }
    if((bus_channel < CONFIG_RTIO_FIRST_DDS_CHANNEL)
       || (bus_channel >= (CONFIG_RTIO_FIRST_DDS_CHANNEL+CONFIG_RTIO_DDS_COUNT))) {
        core_log("Attempted to use invalid DDS bus\n");
        return;
    }
#ifdef CONFIG_DDS_ONEHOT_SEL
    channel_enc = 1 << channel;
#else
    channel_enc = channel;
#endif
    DDS_WRITE(DDS_GPIO, channel_enc << 1);

#ifdef CONFIG_DDS_AD9858
    DDS_WRITE(DDS_FTW0, ftw & 0xff);
    DDS_WRITE(DDS_FTW1, (ftw >> 8) & 0xff);
    DDS_WRITE(DDS_FTW2, (ftw >> 16) & 0xff);
    DDS_WRITE(DDS_FTW3, (ftw >> 24) & 0xff);
#endif

#ifdef CONFIG_DDS_AD9914
    DDS_WRITE(DDS_FTWL, ftw & 0xffff);
    DDS_WRITE(DDS_FTWH, (ftw >> 16) & 0xffff);
#endif

    /* We need the RTIO fine timestamp clock to be phase-locked
     * to DDS SYSCLK, and divided by an integer CONFIG_DDS_RTIO_CLK_RATIO.
     */
    if(phase_mode == PHASE_MODE_CONTINUOUS) {
        /* Do not clear phase accumulator on FUD */
#ifdef CONFIG_DDS_AD9858
        DDS_WRITE(DDS_CFR2, 0x00);
#endif
#ifdef CONFIG_DDS_AD9914
        /* Disable autoclear phase accumulator and enables OSK. */
        DDS_WRITE(DDS_CFR1L, 0x0108);
#endif
        pow += continuous_phase_comp[bus_channel-CONFIG_RTIO_FIRST_DDS_CHANNEL][channel];
    } else {
        long long int fud_time;

        /* Clear phase accumulator on FUD */
#ifdef CONFIG_DDS_AD9858
        DDS_WRITE(DDS_CFR2, 0x40);
#endif
#ifdef CONFIG_DDS_AD9914
        /* Enable autoclear phase accumulator and enables OSK. */
        DDS_WRITE(DDS_CFR1L, 0x2108);
#endif
        fud_time = now + 2*DURATION_WRITE;
        pow -= (ref_time - fud_time)*CONFIG_DDS_RTIO_CLK_RATIO*ftw >> (32-DDS_POW_WIDTH);
        if(phase_mode == PHASE_MODE_TRACKING)
            pow += ref_time*CONFIG_DDS_RTIO_CLK_RATIO*ftw >> (32-DDS_POW_WIDTH);
        continuous_phase_comp[bus_channel-CONFIG_RTIO_FIRST_DDS_CHANNEL][channel] = pow;
    }

#ifdef CONFIG_DDS_AD9858
    DDS_WRITE(DDS_POW0, pow & 0xff);
    DDS_WRITE(DDS_POW1, (pow >> 8) & 0x3f);
#endif
#ifdef CONFIG_DDS_AD9914
    DDS_WRITE(DDS_POW, pow);
#endif
#ifdef CONFIG_DDS_AD9914
    DDS_WRITE(DDS_ASF, amplitude);
#endif
    DDS_WRITE(DDS_FUD, 0);
}

struct dds_set_params {
    int bus_channel;
    int channel;
    unsigned int ftw;
    unsigned int pow;
    int phase_mode;
    unsigned int amplitude;
};

static int batch_mode;
static int batch_count;
static long long int batch_ref_time;
static struct dds_set_params batch[DDS_MAX_BATCH];

void dds_batch_enter(long long int timestamp)
{
    if(batch_mode)
        artiq_raise_from_c("DDSBatchError", "DDS batch error", 0, 0, 0);
    batch_mode = 1;
    batch_count = 0;
    batch_ref_time = timestamp;
}

void dds_batch_exit(void)
{
    long long int now;
    int i;

    if(!batch_mode)
        artiq_raise_from_c("DDSBatchError", "DDS batch error", 0, 0, 0);
    /* + FUD time */
    now = batch_ref_time - batch_count*(DURATION_PROGRAM + DURATION_WRITE);
    for(i=0;i<batch_count;i++) {
        dds_set_one(now, batch_ref_time,
            batch[i].bus_channel, batch[i].channel,
            batch[i].ftw, batch[i].pow, batch[i].phase_mode,
            batch[i].amplitude);
        now += DURATION_PROGRAM + DURATION_WRITE;
    }
    batch_mode = 0;
}

void dds_set(long long int timestamp, int bus_channel, int channel,
    unsigned int ftw, unsigned int pow, int phase_mode, unsigned int amplitude)
{
    if(batch_mode) {
        if(batch_count >= DDS_MAX_BATCH)
            artiq_raise_from_c("DDSBatchError", "DDS batch error", 0, 0, 0);
        /* timestamp parameter ignored (determined by batch) */
        batch[batch_count].bus_channel = bus_channel;
        batch[batch_count].channel = channel;
        batch[batch_count].ftw = ftw;
        batch[batch_count].pow = pow;
        batch[batch_count].phase_mode = phase_mode;
        batch[batch_count].amplitude = amplitude;
        batch_count++;
    } else {
        dds_set_one(timestamp - DURATION_PROGRAM, timestamp,
                    bus_channel, channel,
                    ftw, pow, phase_mode, amplitude);
    }
}
