#include <string.h>
#include <stdarg.h>

#include <generated/csr.h>

#ifdef ARTIQ_AMP
#include "mailbox.h"
#include "messages.h"
#else
#include <system.h>
#include "exceptions.h"
#include "rtio.h"
#include "dds.h"
#endif

#include "log.h"
#include "kloader.h"
#include "exceptions.h"
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
    buffer_out_index_data = 0;
    buffer_out_index_mem = 0;
    memset(&buffer_out[4], 0, 4);
#ifdef ARTIQ_AMP
    kloader_stop_kernel();
#endif
    user_kernel_state = USER_KERNEL_NONE;
}

void session_end(void)
{
#ifdef ARTIQ_AMP
    kloader_stop_kernel();
    kloader_start_idle_kernel();
#endif
}

/* host to device */
enum {
    REMOTEMSG_TYPE_LOG_REQUEST = 1,
    REMOTEMSG_TYPE_IDENT_REQUEST,
    REMOTEMSG_TYPE_SWITCH_CLOCK,
    
    REMOTEMSG_TYPE_LOAD_OBJECT,
    REMOTEMSG_TYPE_RUN_KERNEL,

    REMOTEMSG_TYPE_RPC_REPLY
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
};

static int add_rpc_value(int bi, int type_tag, void *value)
{
    char base_type;
    int obi, r;
    int i, p;
    int len;

    obi = bi;
    base_type = type_tag;

    if((bi + 1) > BUFFER_OUT_SIZE)
        return -1;
    buffer_out[bi++] = base_type;

    switch(base_type) {
        case 'n':
            return bi - obi;
        case 'b':
            if((bi + 1) > BUFFER_OUT_SIZE)
                return -1;
            if(*(char *)value)
                buffer_out[bi++] = 1;
            else
                buffer_out[bi++] = 0;
            return bi - obi;
        case 'i':
            if((bi + 4) > BUFFER_OUT_SIZE)
                return -1;
            memcpy(&buffer_out[bi], value, 4);
            bi += 4;
            return bi - obi;
        case 'I':
        case 'f':
            if((bi + 8) > BUFFER_OUT_SIZE)
                return -1;
            memcpy(&buffer_out[bi], value, 8);
            bi += 8;
            return bi - obi;
        case 'F':
            if((bi + 16) > BUFFER_OUT_SIZE)
                return -1;
            memcpy(&buffer_out[bi], value, 16);
            bi += 16;
            return bi - obi;
        case 'l':
            len = *(int *)value;
            p = 4;
            for(i=0;i<len;i++) {
                r = add_rpc_value(bi, type_tag >> 8, (char *)value + p);
                if(r < 0)
                    return r;
                bi += r;
                p += r;
            }
            if((bi + 1) > BUFFER_OUT_SIZE)
                return -1;
            buffer_out[bi++] = 0;
            return bi - obi;
    }
    return -1;
}

static int send_rpc_request(int rpc_num, va_list args)
{
    int r;
    int bi = 8;
    int type_tag;
    
    buffer_out[bi++] = REMOTEMSG_TYPE_RPC_REQUEST;
    
    memcpy(&buffer_out[bi], &rpc_num, 4);
    bi += 4;

    while((type_tag = va_arg(args, int))) {
        r = add_rpc_value(bi, type_tag,
            type_tag == 'n' ? NULL : va_arg(args, void *));
        if(bi < 0)
            return 0;
        bi += r;
    }
    if((bi + 1) > BUFFER_OUT_SIZE)
        return 0;
    buffer_out[bi++] = 0;

    submit_output(bi);
    return 1;
}

#ifndef ARTIQ_AMP
static int rpc_reply_eid;
static int rpc_reply_retval;

int rpc(int rpc_num, ...)
{
    va_list args;

    va_start(args, rpc_num);
    send_rpc_request(rpc_num, args);
    va_end(args);

    user_kernel_state = USER_KERNEL_WAIT_RPC;
    /*while(user_kernel_state == USER_KERNEL_WAIT_RPC)
        comm_service();*/

    if(rpc_reply_eid != EID_NONE)
        exception_raise(rpc_reply_eid);
    return rpc_reply_retval;
}

/* assumes output buffer is empty when called */
static void run_kernel_up(kernel_function k)
{
    void *jb;
    int eid;
    long long eparams[3];

    jb = exception_push();
    if(exception_setjmp(jb)) {
        eid = exception_getid(eparams);
        buffer_out[8] = REMOTEMSG_TYPE_KERNEL_EXCEPTION;
        memcpy(&buffer_out[9], &eid, 4);
        memcpy(&buffer_out[13], eparams, 3*8);
        submit_output(9+4+3*8);
    } else {
        dds_init();
        rtio_init();
        flush_cpu_icache();
        k();
        exception_pop(1);
        buffer_out[8] = REMOTEMSG_TYPE_KERNEL_FINISHED;
        submit_output(9);
    }
}
#endif /* !ARTIQ_AMP */

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
            rtiocrg_clock_sel_write(buffer_in[9]);
            buffer_out[8] = REMOTEMSG_TYPE_CLOCK_SWITCH_COMPLETED;
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

#ifdef ARTIQ_AMP
            kloader_start_user_kernel(k);
            user_kernel_state = USER_KERNEL_RUNNING;
#else
            user_kernel_state = USER_KERNEL_RUNNING;
            run_kernel_up(k);
            user_kernel_state = USER_KERNEL_LOADED;
#endif
            break;
        }
        case REMOTEMSG_TYPE_RPC_REPLY: {
#ifdef ARTIQ_AMP
            struct msg_rpc_reply reply;
#endif

            if(user_kernel_state != USER_KERNEL_WAIT_RPC) {
                log("Unsolicited RPC reply");
                return 0;
            }

#ifdef ARTIQ_AMP
            reply.type = MESSAGE_TYPE_RPC_REPLY;
            memcpy(&reply.eid, &buffer_in[9], 4);
            memcpy(&reply.retval, &buffer_in[13], 4);
            mailbox_send_and_wait(&reply);
#else
            memcpy(&rpc_reply_eid, &buffer_in[9], 4);
            memcpy(&rpc_reply_retval, &buffer_in[13], 4);
#endif
            user_kernel_state = USER_KERNEL_RUNNING;
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

#ifdef ARTIQ_AMP
/* assumes output buffer is empty when called */
static void process_kmsg(struct msg_base *umsg)
{
    if(user_kernel_state != USER_KERNEL_RUNNING) {
        log("Received message from kernel CPU while not in running state");
        return;
    }

    switch(umsg->type) {
        case MESSAGE_TYPE_FINISHED:
            buffer_out[8] = REMOTEMSG_TYPE_KERNEL_FINISHED;
            submit_output(9);

            kloader_stop_kernel();
            user_kernel_state = USER_KERNEL_LOADED;
            break;
        case MESSAGE_TYPE_EXCEPTION: {
            struct msg_exception *msg = (struct msg_exception *)umsg;

            buffer_out[8] = REMOTEMSG_TYPE_KERNEL_EXCEPTION;
            memcpy(&buffer_out[9], &msg->eid, 4);
            memcpy(&buffer_out[13], msg->eparams, 3*8);
            submit_output(9+4+3*8);

            kloader_stop_kernel();
            user_kernel_state = USER_KERNEL_LOADED;
            break;
        }
        case MESSAGE_TYPE_RPC_REQUEST: {
            struct msg_rpc_request *msg = (struct msg_rpc_request *)umsg;

            send_rpc_request(msg->rpc_num, msg->args);
            user_kernel_state = USER_KERNEL_WAIT_RPC;
            break;
        }
        case MESSAGE_TYPE_LOG: {
            struct msg_log *msg = (struct msg_log *)umsg;

            log(msg->fmt, msg->args);
            break;
        }
        default: {
            int eid;

            log("Received invalid message type from kernel CPU");

            buffer_out[8] = REMOTEMSG_TYPE_KERNEL_EXCEPTION;
            eid = EID_INTERNAL_ERROR;
            memcpy(&buffer_out[9], &eid, 4);
            memset(&buffer_out[13], 0, 3*8);
            submit_output(9+4+3*8);

            kloader_stop_kernel();
            user_kernel_state = USER_KERNEL_LOADED;
            break;
        }
    }
}
#endif /* ARTIQ_AMP */

void session_poll(void **data, int *len)
{
    int l;

    l = get_out_packet_len();

#ifdef ARTIQ_AMP
    /* If the output buffer is available, 
     * check if the kernel CPU has something to transmit.
     */
    if(l == 0) {
        struct msg_base *umsg;

        umsg = mailbox_receive();
        if(umsg) {
            process_kmsg(umsg);
            mailbox_acknowledge();
        }
        l = get_out_packet_len();
    }
#endif

    *len = l - buffer_out_index_data;
    *data = &buffer_out[buffer_out_index_data];
}

void session_ack_data(int len)
{
    buffer_out_index_data += len;
}

void session_ack_mem(int len)
{
    buffer_out_index_mem += len;
    if(buffer_out_index_mem >= get_out_packet_len()) {
        memset(&buffer_out[4], 0, 4);
        buffer_out_index_mem = 0;
    }
}
