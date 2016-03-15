#include <system.h>
#include <generated/csr.h>

#include "log.h"
#include "analyzer.h"


#ifdef CSR_RTIO_ANALYZER_BASE

struct analyzer_header {
    unsigned int sent_bytes;
    unsigned long long int total_byte_count;
    unsigned char overflow_occured;
    unsigned char log_channel;
    unsigned char dds_onehot_sel;
} __attribute__((packed));


#define ANALYZER_BUFFER_SIZE (512*1024)

static struct analyzer_header analyzer_header;
static char analyzer_buffer[ANALYZER_BUFFER_SIZE] __attribute__((aligned(64)));

static void arm(void)
{
    rtio_analyzer_message_encoder_overflow_reset_write(1);
    rtio_analyzer_dma_base_address_write((unsigned int)analyzer_buffer);
    rtio_analyzer_dma_last_address_write((unsigned int)analyzer_buffer + ANALYZER_BUFFER_SIZE - 1);
    rtio_analyzer_dma_reset_write(1);
    rtio_analyzer_enable_write(1);
}

static void disarm(void)
{
    rtio_analyzer_enable_write(0);
    while(rtio_analyzer_busy_read());
    flush_cpu_dcache();
    flush_l2_cache();
}

void analyzer_init(void)
{
    arm();
}

enum {
    SEND_STATE_HEADER,
    SEND_STATE_POST_POINTER, /* send from pointer to end of buffer */
    SEND_STATE_PRE_POINTER, /* send from start of buffer to pointer-1 */
    SEND_STATE_TERMINATE
};

static int send_state;
static int pointer;
static int wraparound;
static int offset_consumed;
static int offset_sent;

void analyzer_start(void)
{
    disarm();

    analyzer_header.total_byte_count = rtio_analyzer_dma_byte_count_read();
    pointer = analyzer_header.total_byte_count % ANALYZER_BUFFER_SIZE;
    wraparound = analyzer_header.total_byte_count >= ANALYZER_BUFFER_SIZE;

    if(wraparound)
        analyzer_header.sent_bytes = ANALYZER_BUFFER_SIZE;
    else
        analyzer_header.sent_bytes = analyzer_header.total_byte_count;

    analyzer_header.overflow_occured = rtio_analyzer_message_encoder_overflow_read();
    analyzer_header.log_channel = CONFIG_RTIO_LOG_CHANNEL;
#ifdef CONFIG_DDS_ONEHOT_SEL
    analyzer_header.dds_onehot_sel = 1;
#else
    analyzer_header.dds_onehot_sel = 0;
#endif

    offset_consumed = 0;
    offset_sent = 0;
    send_state = SEND_STATE_HEADER;
}

void analyzer_end(void)
{
    arm();
}

int analyzer_input(void *data, int length)
{
    core_log("no input should be received by analyzer, dropping connection\n");
    return -1;
}

void analyzer_poll(void **data, int *length)
{
    switch(send_state) {
        case SEND_STATE_HEADER:
            *length = sizeof(struct analyzer_header) - offset_consumed;
            *data = (char *)&analyzer_header + offset_consumed;
            break;
        case SEND_STATE_POST_POINTER:
            *length = ANALYZER_BUFFER_SIZE - pointer - offset_consumed;
            *data = analyzer_buffer + pointer + offset_consumed;
            break;
        case SEND_STATE_PRE_POINTER:
            *length = pointer - offset_consumed;
            *data = analyzer_buffer + offset_consumed;
            break;
        case SEND_STATE_TERMINATE:
            *length = -1;
            break;
        default:
            *length = 0;
            break;
    }
}

void analyzer_ack_consumed(int length)
{
    offset_consumed += length;
}

void analyzer_ack_sent(int length)
{
    offset_sent += length;
    switch(send_state) {
        case SEND_STATE_HEADER:
            if(offset_sent >= sizeof(struct analyzer_header)) {
                offset_consumed = 0;
                offset_sent = 0;
                if(wraparound)
                    send_state = SEND_STATE_POST_POINTER;
                else {
                    if(pointer)
                        send_state = SEND_STATE_PRE_POINTER;
                    else
                        send_state = SEND_STATE_TERMINATE;
                }
            }
            break;
        case SEND_STATE_POST_POINTER:
            if(pointer + offset_consumed >= ANALYZER_BUFFER_SIZE) {
                offset_consumed = 0;
                offset_sent = 0;
                send_state = SEND_STATE_PRE_POINTER;
            }
            break;
        case SEND_STATE_PRE_POINTER:
            if(offset_sent >= pointer)
                send_state = SEND_STATE_TERMINATE;
            break;
    }
}

#endif
