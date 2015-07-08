#include <generated/csr.h>
#include <stdio.h>

#include "exceptions.h"
#include "rtio.h"
#include "log.h"
#include "dds.h"

#define DURATION_WRITE (5 << RTIO_FINE_TS_WIDTH)

#if defined DDS_AD9858
/* Assume 8-bit bus */
#define DURATION_INIT (7*DURATION_WRITE) /* not counting FUD */
#define DURATION_PROGRAM (8*DURATION_WRITE) /* not counting FUD */

#elif defined DDS_AD9914
/* Assume 16-bit bus */
/* DAC calibration takes max. 135us as per datasheet. Take a good margin. */
#define DURATION_DAC_CAL (30000 << RTIO_FINE_TS_WIDTH)
/* not counting final FUD */
#define DURATION_INIT (8*DURATION_WRITE + DURATION_DAC_CAL)
#define DURATION_PROGRAM (5*DURATION_WRITE) /* not counting FUD */

#else
#error Unknown DDS configuration
#endif

#define DDS_WRITE(addr, data) do { \
        rtio_o_address_write(addr); \
        rtio_o_data_write(data); \
        rtio_o_timestamp_write(now); \
        rtio_write_and_process_status(now, RTIO_DDS_CHANNEL); \
        now += DURATION_WRITE; \
    } while(0)

void dds_init_all(void)
{
    int i;
    long long int now;

    now = rtio_get_counter() + 10000;
    for(i=0;i<DDS_CHANNEL_COUNT;i++) {
        dds_init(now, i);
        now += DURATION_INIT + DURATION_WRITE; /* + FUD time */
    }
    while(rtio_get_counter() < now);
}

void dds_init(long long int timestamp, int channel)
{
    long long int now;

    rtio_chan_sel_write(RTIO_DDS_CHANNEL);

    now = timestamp - DURATION_INIT;

#ifdef DDS_ONEHOT_SEL
    channel = 1 << channel;
#endif
    channel <<= 1;
    DDS_WRITE(DDS_GPIO, channel);
    DDS_WRITE(DDS_GPIO, channel | 1); /* reset */
    DDS_WRITE(DDS_GPIO, channel);

#ifdef DDS_AD9858
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

#ifdef DDS_AD9914
    /*
     * Enable cosine output (to match AD9858 behavior)
     * Enable DAC calibration
     * Leave SYNCLK enabled and PLL/divider disabled
     */
    DDS_WRITE(DDS_CFR1L, 0x0008);
    DDS_WRITE(DDS_CFR1H, 0x0000);
    DDS_WRITE(DDS_CFR4H, 0x0105);
    DDS_WRITE(DDS_FUD, 0);
    /* Disable DAC calibration */
    now += DURATION_DAC_CAL;
    DDS_WRITE(DDS_CFR4H, 0x0005);
    DDS_WRITE(DDS_FUD, 0);
#endif
}

/* Compensation to keep phase continuity when switching from absolute or tracking
 * to continuous phase mode. */
static unsigned int continuous_phase_comp[DDS_CHANNEL_COUNT];

static void dds_set_one(long long int now, long long int ref_time, unsigned int channel,
    unsigned int ftw, unsigned int pow, int phase_mode)
{
    unsigned int channel_enc;

	if(channel >= DDS_CHANNEL_COUNT) {
		log("Attempted to set invalid DDS channel");
		return;
	}
#ifdef DDS_ONEHOT_SEL
    channel_enc = 1 << channel;
#else
    channel_enc = channel;
#endif
    DDS_WRITE(DDS_GPIO, channel_enc << 1);

#ifdef DDS_AD9858
    DDS_WRITE(DDS_FTW0, ftw & 0xff);
    DDS_WRITE(DDS_FTW1, (ftw >> 8) & 0xff);
    DDS_WRITE(DDS_FTW2, (ftw >> 16) & 0xff);
    DDS_WRITE(DDS_FTW3, (ftw >> 24) & 0xff);
#endif

#ifdef DDS_AD9914
    DDS_WRITE(DDS_FTWL, ftw & 0xffff);
    DDS_WRITE(DDS_FTWH, (ftw >> 16) & 0xffff);
#endif

    /* We need the RTIO fine timestamp clock to be phase-locked
     * to DDS SYSCLK, and divided by an integer DDS_RTIO_CLK_RATIO.
     */
    if(phase_mode == PHASE_MODE_CONTINUOUS) {
        /* Do not clear phase accumulator on FUD */
#ifdef DDS_AD9858
        DDS_WRITE(DDS_CFR2, 0x00);
#endif
#ifdef DDS_AD9914
        DDS_WRITE(DDS_CFR1L, 0x0008);
#endif
        pow += continuous_phase_comp[channel];
    } else {
        long long int fud_time;

        /* Clear phase accumulator on FUD */
#ifdef DDS_AD9858
        DDS_WRITE(DDS_CFR2, 0x40);
#endif
#ifdef DDS_AD9914
        DDS_WRITE(DDS_CFR1L, 0x2008);
#endif
        fud_time = now + 2*DURATION_WRITE;
        pow -= (ref_time - fud_time)*DDS_RTIO_CLK_RATIO*ftw >> (32-DDS_POW_WIDTH);
        if(phase_mode == PHASE_MODE_TRACKING)
            pow += ref_time*DDS_RTIO_CLK_RATIO*ftw >> (32-DDS_POW_WIDTH);
        continuous_phase_comp[channel] = pow;
    }

#ifdef DDS_AD9858
    DDS_WRITE(DDS_POW0, pow & 0xff);
    DDS_WRITE(DDS_POW1, (pow >> 8) & 0x3f);
#endif
#ifdef DDS_AD9914
    DDS_WRITE(DDS_POW, pow);
#endif
    DDS_WRITE(DDS_FUD, 0);
}

struct dds_set_params {
    int channel;
    unsigned int ftw;
    unsigned int pow;
    int phase_mode;
};

static int batch_mode;
static int batch_count;
static long long int batch_ref_time;
static struct dds_set_params batch[DDS_MAX_BATCH];

void dds_batch_enter(long long int timestamp)
{
    if(batch_mode)
        exception_raise(EID_DDS_BATCH_ERROR);
    batch_mode = 1;
    batch_count = 0;
    batch_ref_time = timestamp;
}

void dds_batch_exit(void)
{
    long long int now;
    int i;

    if(!batch_mode)
        exception_raise(EID_DDS_BATCH_ERROR);
    rtio_chan_sel_write(RTIO_DDS_CHANNEL);
    /* + FUD time */
    now = batch_ref_time - batch_count*(DURATION_PROGRAM + DURATION_WRITE);
    for(i=0;i<batch_count;i++) {
        dds_set_one(now, batch_ref_time,
            batch[i].channel, batch[i].ftw, batch[i].pow, batch[i].phase_mode);
        now += DURATION_PROGRAM + DURATION_WRITE;
    }
    batch_mode = 0;
}

void dds_set(long long int timestamp, int channel,
    unsigned int ftw, unsigned int pow, int phase_mode)
{
    if(batch_mode) {
        if(batch_count >= DDS_MAX_BATCH)
            exception_raise(EID_DDS_BATCH_ERROR);
        /* timestamp parameter ignored (determined by batch) */
        batch[batch_count].channel = channel;
        batch[batch_count].ftw = ftw;
        batch[batch_count].pow = pow;
        batch[batch_count].phase_mode = phase_mode;
        batch_count++;
    } else {
        rtio_chan_sel_write(RTIO_DDS_CHANNEL);
        dds_set_one(timestamp - DURATION_PROGRAM, timestamp, channel, ftw, pow, phase_mode);
    }
}
