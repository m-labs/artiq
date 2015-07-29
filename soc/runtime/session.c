#include <string.h>
#include <stdio.h>
#include <stdarg.h>

#include <generated/csr.h>

#include "mailbox.h"
#include "messages.h"

#include "clock.h"
#include "log.h"
#include "kloader.h"
#include "exceptions.h"
#include "flash_storage.h"
#include "rtiocrg.h"
#include "session.h"

#define BUFFER_IN_SIZE (1024*1024)
#define BUFFER_OUT_SIZE (1024*1024)

static int buffer_in_index;
/* The 9th byte (right after the header) of buffer_in must be aligned 
 * to a 32-bit boundary for elf_loader to work.
 */
static struct {
    char padding[3];
    char data[BUFFER_IN_SIZE];
} __attribute__((packed)) _buffer_in __attribute__((aligned(4)));
#define buffer_in _buffer_in.data
static int buffer_out_index_data;
static int buffer_out_index_mem;
static char buffer_out[BUFFER_OUT_SIZE];

static int get_in_packet_len(void)
{
    int r;

    memcpy(&r, &buffer_in[4], 4);
    return r;
}

static int get_out_packet_len(void)
{
    int r;

    memcpy(&r, &buffer_out[4], 4);
    return r;
}

static void submit_output(int len)
{
    memset(&buffer_out[0], 0x5a, 4);
    memcpy(&buffer_out[4], &len, 4);
    buffer_out_index_data = 0;
    buffer_out_index_mem = 0;
}

static int user_kernel_state;

enum {
    USER_KERNEL_NONE = 0,
    USER_KERNEL_LOADED,
    USER_KERNEL_RUNNING,
    USER_KERNEL_WAIT_RPC /* < must come after _RUNNING */
};

void session_start(void)
{
    buffer_in_index = 0;
    memset(&buffer_out[4], 0, 4);
    kloader_stop();
    user_kernel_state = USER_KERNEL_NONE;
    now = -1;
}

void session_end(void)
{
    kloader_stop();
    now = -1;
    kloader_start_idle_kernel();
}

/* host to device */
enum {
    REMOTEMSG_TYPE_LOG_REQUEST = 1,
    REMOTEMSG_TYPE_IDENT_REQUEST,
    REMOTEMSG_TYPE_SWITCH_CLOCK,
    
    REMOTEMSG_TYPE_LOAD_OBJECT,
    REMOTEMSG_TYPE_RUN_KERNEL,

    REMOTEMSG_TYPE_RPC_REPLY,

    REMOTEMSG_TYPE_FLASH_READ_REQUEST,
    REMOTEMSG_TYPE_FLASH_WRITE_REQUEST,
    REMOTEMSG_TYPE_FLASH_ERASE_REQUEST,
    REMOTEMSG_TYPE_FLASH_REMOVE_REQUEST
};

/* device to host */
enum {
    REMOTEMSG_TYPE_LOG_REPLY = 1,
    REMOTEMSG_TYPE_IDENT_REPLY,
    REMOTEMSG_TYPE_CLOCK_SWITCH_COMPLETED,
    REMOTEMSG_TYPE_CLOCK_SWITCH_FAILED,

    REMOTEMSG_TYPE_LOAD_COMPLETED,
    REMOTEMSG_TYPE_LOAD_FAILED,

    REMOTEMSG_TYPE_KERNEL_FINISHED,
    REMOTEMSG_TYPE_KERNEL_STARTUP_FAILED,
    REMOTEMSG_TYPE_KERNEL_EXCEPTION,

    REMOTEMSG_TYPE_RPC_REQUEST,

    REMOTEMSG_TYPE_FLASH_READ_REPLY,
    REMOTEMSG_TYPE_FLASH_OK_REPLY,
    REMOTEMSG_TYPE_FLASH_ERROR_REPLY
};

static int check_flash_storage_key_len(char *key, unsigned int key_len)
{
    if(key_len == get_in_packet_len() - 8) {
        log("Invalid key: not a null-terminated string");
        buffer_out[8] = REMOTEMSG_TYPE_FLASH_ERROR_REPLY;
        submit_output(9);
        return 0;
    }
    return 1;
}

static int process_input(void)
{
    switch(buffer_in[8]) {
        case REMOTEMSG_TYPE_LOG_REQUEST:
#if (LOG_BUFFER_SIZE + 9) > BUFFER_OUT_SIZE
#error Output buffer cannot hold the log buffer
#endif
            buffer_out[8] = REMOTEMSG_TYPE_LOG_REPLY;
            log_get(&buffer_out[9]);
            submit_output(9 + LOG_BUFFER_SIZE);
            break;
        case REMOTEMSG_TYPE_IDENT_REQUEST:
            buffer_out[8] = REMOTEMSG_TYPE_IDENT_REPLY;
            buffer_out[9] = 'A';
            buffer_out[10] = 'R';
            buffer_out[11] = 'O';
            buffer_out[12] = 'R';
            submit_output(13);
            break;
        case REMOTEMSG_TYPE_SWITCH_CLOCK:
            if(user_kernel_state >= USER_KERNEL_RUNNING) {
                log("Attempted to switch RTIO clock while kernel running");
                buffer_out[8] = REMOTEMSG_TYPE_CLOCK_SWITCH_FAILED;
                submit_output(9);
                break;
            }
            if(rtiocrg_switch_clock(buffer_in[9]))
                buffer_out[8] = REMOTEMSG_TYPE_CLOCK_SWITCH_COMPLETED;
            else
                buffer_out[8] = REMOTEMSG_TYPE_CLOCK_SWITCH_FAILED;
            submit_output(9);
            break;
        case REMOTEMSG_TYPE_LOAD_OBJECT:
            if(user_kernel_state >= USER_KERNEL_RUNNING) {
                log("Attempted to load new kernel while already running");
                buffer_out[8] = REMOTEMSG_TYPE_LOAD_FAILED;
                submit_output(9);
                break;    
            }
            if(kloader_load(&buffer_in[9], get_in_packet_len() - 8)) {
                buffer_out[8] = REMOTEMSG_TYPE_LOAD_COMPLETED;
                user_kernel_state = USER_KERNEL_LOADED;
            } else
                buffer_out[8] = REMOTEMSG_TYPE_LOAD_FAILED;
            submit_output(9);
            break;
        case REMOTEMSG_TYPE_RUN_KERNEL: {
            kernel_function k;

            if(user_kernel_state != USER_KERNEL_LOADED) {
                log("Attempted to run kernel while not in the LOADED state");
                buffer_out[8] = REMOTEMSG_TYPE_KERNEL_STARTUP_FAILED;
                submit_output(9);
                break;
            }

            if((buffer_in_index + 1) > BUFFER_OUT_SIZE) {
                log("Kernel name too long");
                buffer_out[8] = REMOTEMSG_TYPE_KERNEL_STARTUP_FAILED;
                submit_output(9);
                break;
            }
            buffer_in[buffer_in_index] = 0;

            k = kloader_find((char *)&buffer_in[9]);
            if(k == NULL) {
                log("Failed to find kernel entry point '%s' in object", &buffer_in[9]);
                buffer_out[8] = REMOTEMSG_TYPE_KERNEL_STARTUP_FAILED;
                submit_output(9);
                break;
            }

            watchdog_init();
            kloader_start_user_kernel(k);
            user_kernel_state = USER_KERNEL_RUNNING;
            break;
        }
        case REMOTEMSG_TYPE_RPC_REPLY: {
            struct msg_rpc_reply reply;

            if(user_kernel_state != USER_KERNEL_WAIT_RPC) {
                log("Unsolicited RPC reply");
                return 0;
            }

            reply.type = MESSAGE_TYPE_RPC_REPLY;
            memcpy(&reply.eid, &buffer_in[9], 4);
            memcpy(&reply.retval, &buffer_in[13], 4);
            mailbox_send_and_wait(&reply);
            user_kernel_state = USER_KERNEL_RUNNING;
            break;
        }
        case REMOTEMSG_TYPE_FLASH_READ_REQUEST: {
#if SPIFLASH_SECTOR_SIZE - 4 > BUFFER_OUT_SIZE - 9
#error Output buffer cannot hold the flash storage data
#elif SPIFLASH_SECTOR_SIZE - 4 > BUFFER_IN_SIZE - 9
#error Input buffer cannot hold the flash storage data
#endif
            unsigned int ret, in_packet_len;
            char *key;

            in_packet_len = get_in_packet_len();
            key = &buffer_in[9];
            buffer_in[in_packet_len] = '\0';

            buffer_out[8] = REMOTEMSG_TYPE_FLASH_READ_REPLY;
            ret = fs_read(key, &buffer_out[9], sizeof(buffer_out) - 9, NULL);
            submit_output(9 + ret);
            break;
        }
        case REMOTEMSG_TYPE_FLASH_WRITE_REQUEST: {
            char *key, *value;
            unsigned int key_len, value_len, in_packet_len;
            int ret;

            in_packet_len = get_in_packet_len();
            key = &buffer_in[9];
            key_len = strnlen(key, in_packet_len - 9) + 1;
            if(!check_flash_storage_key_len(key, key_len))
                break;

            value_len = in_packet_len - key_len - 9;
            value = key + key_len;
            ret = fs_write(key, value, value_len);

            if(ret)
                buffer_out[8] = REMOTEMSG_TYPE_FLASH_OK_REPLY;
            else
                buffer_out[8] = REMOTEMSG_TYPE_FLASH_ERROR_REPLY;
            submit_output(9);
            break;
        }
        case REMOTEMSG_TYPE_FLASH_ERASE_REQUEST: {
            fs_erase();
            buffer_out[8] = REMOTEMSG_TYPE_FLASH_OK_REPLY;
            submit_output(9);
            break;
        }
        case REMOTEMSG_TYPE_FLASH_REMOVE_REQUEST: {
            char *key;
            unsigned int in_packet_len;

            in_packet_len = get_in_packet_len();
            key = &buffer_in[9];
            buffer_in[in_packet_len] = '\0';

            fs_remove(key);
            buffer_out[8] = REMOTEMSG_TYPE_FLASH_OK_REPLY;
            submit_output(9);
            break;
        }
        default:
            return 0;
    }
    return 1;
}

/* Returns -1 in case of irrecoverable error
 * (the session must be dropped and session_end called)
 */
int session_input(void *data, int len)
{
    unsigned char *_data = data;
    int consumed;

    consumed = 0;
    while(len > 0) {
        /* Make sure the output buffer is available for any reply
         * we might need to send. */
        if(get_out_packet_len() != 0)
            return consumed;

        if(buffer_in_index < 4) {
            /* synchronizing */
            if(_data[consumed] == 0x5a)
                buffer_in[buffer_in_index++] = 0x5a;
            else
                buffer_in_index = 0;
            consumed++; len--;
        } else if(buffer_in_index < 8) {
            /* receiving length */
            buffer_in[buffer_in_index++] = _data[consumed];
            consumed++; len--;
            if((buffer_in_index == 8) && (get_in_packet_len() == 0))
                /* zero-length packet = session reset */
                return -2;
        } else {
            /* receiving payload */
            int packet_len;
            int count;

            packet_len = get_in_packet_len();
            if(packet_len > BUFFER_IN_SIZE)
                return -1;
            count = packet_len - buffer_in_index;
            if(count > len)
                count = len;
            memcpy(&buffer_in[buffer_in_index], &_data[consumed], count);
            buffer_in_index += count;

            if(buffer_in_index == packet_len) {
                if(!process_input())
                    return -1;
                buffer_in_index = 0;
            }

            consumed += count; len -= count;
        }
    }
    return consumed;
}

static int add_base_rpc_value(char base_type, void *value, char *buffer_out, int available_space)
{
    switch(base_type) {
        case 'n':
            return 0;
        case 'b':
            if(available_space < 1)
                return -1;
            if(*(char *)value)
                buffer_out[0] = 1;
            else
                buffer_out[0] = 0;
            return 1;
        case 'i':
            if(available_space < 4)
                return -1;
            memcpy(buffer_out, value, 4);
            return 4;
        case 'I':
        case 'f':
            if(available_space < 8)
                return -1;
            memcpy(buffer_out, value, 8);
            return 8;
        case 'F':
            if(available_space < 16)
                return -1;
            memcpy(buffer_out, value, 16);
            return 16;
        default:
            return -1;
    }
}

static int add_rpc_value(int bi, int type_tag, void *value)
{
    char base_type;
    int obi, r;

    obi = bi;
    base_type = type_tag;

    if((bi + 1) > BUFFER_OUT_SIZE)
        return -1;
    buffer_out[bi++] = base_type;

    if(base_type == 'l') {
        char elt_type;
        int len;
        int i, p;

        elt_type = type_tag >> 8;
        if((bi + 1) > BUFFER_OUT_SIZE)
            return -1;
        buffer_out[bi++] = elt_type;

        len = *(int *)value;
        if((bi + 4) > BUFFER_OUT_SIZE)
            return -1;
        memcpy(&buffer_out[bi], &len, 4);
        bi += 4;

        p = 4;
        for(i=0;i<len;i++) {
            r = add_base_rpc_value(elt_type, (char *)value + p,
                                   &buffer_out[bi], BUFFER_OUT_SIZE - bi);
            if(r < 0)
                return r;
            bi += r;
            p += r;
        }
    } else {
        r = add_base_rpc_value(base_type, value,
                               &buffer_out[bi], BUFFER_OUT_SIZE - bi);
        if(r < 0)
            return r;
        bi += r;
    }

    return bi - obi;
}

static int send_rpc_request(int rpc_num, va_list args)
{
    int r;
    int bi = 8;
    int type_tag;
    void *v;

    buffer_out[bi++] = REMOTEMSG_TYPE_RPC_REQUEST;

    memcpy(&buffer_out[bi], &rpc_num, 4);
    bi += 4;

    while((type_tag = va_arg(args, int))) {
        if(type_tag == 'n')
            v = NULL;
        else {
            v = va_arg(args, void *);
            if(!kloader_validate_kpointer(v))
                return 0;
        }
        r = add_rpc_value(bi, type_tag, v);
        if(r < 0)
            return 0;
        bi += r;
    }
    if((bi + 1) > BUFFER_OUT_SIZE)
        return 0;
    buffer_out[bi++] = 0;

    submit_output(bi);
    return 1;
}

/* assumes output buffer is empty when called */
static int process_kmsg(struct msg_base *umsg)
{
    if(!kloader_validate_kpointer(umsg))
        return 0;
    if(kloader_is_essential_kmsg(umsg->type))
        return 1; /* handled elsewhere */
    if(user_kernel_state != USER_KERNEL_RUNNING) {
        log("Received unexpected message from kernel CPU while not in running state");
        return 0;
    }

    switch(umsg->type) {
        case MESSAGE_TYPE_FINISHED:
            buffer_out[8] = REMOTEMSG_TYPE_KERNEL_FINISHED;
            submit_output(9);

            kloader_stop();
            user_kernel_state = USER_KERNEL_LOADED;
            mailbox_acknowledge();
            break;
        case MESSAGE_TYPE_EXCEPTION: {
            struct msg_exception *msg = (struct msg_exception *)umsg;

            buffer_out[8] = REMOTEMSG_TYPE_KERNEL_EXCEPTION;
            memcpy(&buffer_out[9], &msg->eid, 4);
            memcpy(&buffer_out[13], msg->eparams, 3*8);
            submit_output(9+4+3*8);

            kloader_stop();
            user_kernel_state = USER_KERNEL_LOADED;
            mailbox_acknowledge();
            break;
        }
        case MESSAGE_TYPE_WATCHDOG_SET_REQUEST: {
            struct msg_watchdog_set_request *msg = (struct msg_watchdog_set_request *)umsg;
            struct msg_watchdog_set_reply reply;

            reply.type = MESSAGE_TYPE_WATCHDOG_SET_REPLY;
            reply.id = watchdog_set(msg->ms);
            mailbox_send_and_wait(&reply);
            break;
        }
        case MESSAGE_TYPE_WATCHDOG_CLEAR: {
            struct msg_watchdog_clear *msg = (struct msg_watchdog_clear *)umsg;

            watchdog_clear(msg->id);
            mailbox_acknowledge();
            break;
        }
        case MESSAGE_TYPE_RPC_REQUEST: {
            struct msg_rpc_request *msg = (struct msg_rpc_request *)umsg;

            if(!send_rpc_request(msg->rpc_num, msg->args))
                return 0;
            user_kernel_state = USER_KERNEL_WAIT_RPC;
            mailbox_acknowledge();
            break;
        }
        default: {
            log("Received invalid message type from kernel CPU");
            return 0;
        }
    }
    return 1;
}

/* len is set to -1 in case of irrecoverable error
 * (the session must be dropped and session_end called)
 */
void session_poll(void **data, int *len)
{
    int l;

    if(user_kernel_state == USER_KERNEL_RUNNING) {
        if(watchdog_expired()) {
            log("Watchdog expired");
            *len = -1;
            return;
        }
        if(!rtiocrg_check()) {
            log("RTIO clock failure");
            *len = -1;
            return;
        }
    }

    l = get_out_packet_len();

    /* If the output buffer is available, 
     * check if the kernel CPU has something to transmit.
     */
    if(l == 0) {
        struct msg_base *umsg;

        umsg = mailbox_receive();
        if(umsg) {
            if(!process_kmsg(umsg)) {
                *len = -1;
                return;
            }
        }
        l = get_out_packet_len();
    }

    if(l > 0) {
        *len = l - buffer_out_index_data;
        *data = &buffer_out[buffer_out_index_data];
    } else
        *len = 0;
}

void session_ack_data(int len)
{
    buffer_out_index_data += len;
}

void session_ack_mem(int len)
{
    buffer_out_index_mem += len;
    if(buffer_out_index_mem >= get_out_packet_len())
        memset(&buffer_out[4], 0, 4);
}
