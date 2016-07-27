#include "mailbox.h"
#include "messages.h"
#include "rtio.h"
#include "ttl.h"
#include "dds.h"
#include "bridge.h"

#define TIME_BUFFER (8000 << CONFIG_RTIO_FINE_TS_WIDTH)

static void rtio_output_blind(int channel, int addr, int data)
{
    rtio_chan_sel_write(channel);
#ifdef CSR_RTIO_O_ADDRESS_ADDR
    rtio_o_address_write(addr);
#endif
    rtio_o_data_write(data);
    rtio_o_timestamp_write(rtio_get_counter() + TIME_BUFFER);
    rtio_o_we_write(1);
}

static void dds_write(int bus_channel, int addr, int data)
{
    rtio_output_blind(bus_channel, addr, data);
}

static int dds_read(int bus_channel, int addr)
{
    int r;

#ifdef CONFIG_DDS_AD9858
#define DDS_READ_FLAG 128
#endif
#ifdef CONFIG_DDS_AD9914
#define DDS_READ_FLAG 256
#endif
    dds_write(bus_channel, addr | DDS_READ_FLAG, 0);
    while(rtio_i_status_read() & RTIO_I_STATUS_EMPTY);
    r = rtio_i_data_read();
    rtio_i_re_write(1);
    return r;
}

static void send_ready(void)
{
    struct msg_base msg;

    msg.type = MESSAGE_TYPE_BRG_READY;
    mailbox_send_and_wait(&msg);
}

void bridge_main(void)
{
    struct msg_base *umsg;

    rtio_init();
    send_ready();
    while(1) {
        umsg = mailbox_wait_and_receive();
        switch(umsg->type) {
            case MESSAGE_TYPE_BRG_TTL_OE: {
                struct msg_brg_ttl_out *msg;

                msg = (struct msg_brg_ttl_out *)umsg;
                rtio_output_blind(msg->channel, TTL_OE_ADDR, msg->value);
                mailbox_acknowledge();
                break;
            }
            case MESSAGE_TYPE_BRG_TTL_O: {
                struct msg_brg_ttl_out *msg;

                msg = (struct msg_brg_ttl_out *)umsg;
                rtio_output_blind(msg->channel, TTL_O_ADDR, msg->value);
                mailbox_acknowledge();
                break;
            }
            case MESSAGE_TYPE_BRG_DDS_SEL: {
                struct msg_brg_dds_sel *msg;

                msg = (struct msg_brg_dds_sel *)umsg;
                dds_write(msg->bus_channel, DDS_GPIO, msg->channel << 1);
                mailbox_acknowledge();
                break;
            }
            case MESSAGE_TYPE_BRG_DDS_RESET: {
                unsigned int g;
                struct msg_brg_dds_reset *msg;

                msg = (struct msg_brg_dds_reset *)umsg;
                g = dds_read(msg->bus_channel, DDS_GPIO);
                dds_write(msg->bus_channel, DDS_GPIO, g | 1);
                dds_write(msg->bus_channel, DDS_GPIO, g);

                mailbox_acknowledge();
                break;
            }
            case MESSAGE_TYPE_BRG_DDS_READ_REQUEST: {
                struct msg_brg_dds_read_request *msg;
                struct msg_brg_dds_read_reply rmsg;

                msg = (struct msg_brg_dds_read_request *)umsg;
                rmsg.type = MESSAGE_TYPE_BRG_DDS_READ_REPLY;
                rmsg.data = dds_read(msg->bus_channel, msg->address);
                mailbox_send_and_wait(&rmsg);
                break;
            }
            case MESSAGE_TYPE_BRG_DDS_WRITE: {
                struct msg_brg_dds_write *msg;

                msg = (struct msg_brg_dds_write *)umsg;
                dds_write(msg->bus_channel, msg->address, msg->data);
                mailbox_acknowledge();
                break;
            }
            case MESSAGE_TYPE_BRG_DDS_FUD: {
                struct msg_brg_dds_fud *msg;

                msg = (struct msg_brg_dds_fud *)umsg;
                dds_write(msg->bus_channel, DDS_FUD, 0);
                mailbox_acknowledge();
                break;
            }
            default:
                mailbox_acknowledge();
                break;
        }
    }
}
