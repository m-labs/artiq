#ifndef __DDS_H
#define __DDS_H

void dds_init(void);
void dds_phase_clear_en(int channel, int phase_clear_en);
void dds_program(long long int timestamp, int channel,
    unsigned int ftw, unsigned int pow, unsigned int sysclk_per_microcycle,
    int rt_fud, int phase_tracking);

#endif /* __DDS_H */
