#include <string.h>
#include <stdio.h>
#include <stdarg.h>

#include <generated/csr.h>

#include "mailbox.h"
#include "messages.h"

#include "clock.h"
#include "log.h"
#include "kloader.h"
#include "artiq_personality.h"
#include "flash_storage.h"
#include "rtiocrg.h"
#include "session.h"

#define BUFFER_IN_SIZE (1024*1024)
#define BUFFER_OUT_SIZE (1024*1024)

static int process_input();
static int out_packet_available();

// ============================= Reader interface =============================

// Align the 9th byte (right after the header) of buffer_in so that
// the payload can be deserialized directly from the buffer using word reads.
static struct {
    char padding[3];
    union {
        char data[BUFFER_IN_SIZE];
        struct {
            int32_t sync;
            int32_t length;
            int8_t  type;
        } __attribute__((packed)) header;
    };
} __attribute__((packed, aligned(4))) buffer_in;

static int buffer_in_write_cursor, buffer_in_read_cursor;

static void in_packet_reset()
{
    buffer_in_write_cursor = 0;
    buffer_in_read_cursor  = 0;
}

static int in_packet_fill(uint8_t *data, int length)
{
    int consumed = 0;
    while(consumed < length) {
        /* Make sure the output buffer is available for any reply
         * we might need to send. */
        if(!out_packet_available())
            break;

        if(buffer_in_write_cursor < 4) {
            /* Haven't received the synchronization sequence yet. */
            buffer_in.data[buffer_in_write_cursor++] = data[consumed];

            /* Framing error? */
            if(data[consumed++] != 0x5a) {
                buffer_in_write_cursor = 0;
                continue;
            }
        } else if(buffer_in_write_cursor < 8) {
            /* Haven't received the packet length yet. */
            buffer_in.data[buffer_in_write_cursor++] = data[consumed++];
        } else if(buffer_in.header.length == 0) {
            /* Zero-length packet means session reset. */
            return -2;
        } else if(buffer_in.header.length > BUFFER_IN_SIZE) {
            /* Packet wouldn't fit in the buffer. */
            return -1;
        } else if(buffer_in.header.length > buffer_in_write_cursor) {
            /* Receiving payload. */
            int remaining = buffer_in.header.length - buffer_in_write_cursor;
            int amount = length - consumed > remaining ? remaining : length - consumed;
            memcpy(&buffer_in.data[buffer_in_write_cursor], &data[consumed],
                   amount);
            buffer_in_write_cursor += amount;
            consumed += amount;
        }

        if(buffer_in.header.length == buffer_in_write_cursor) {
            /* We have a complete packet. */

            buffer_in_read_cursor = sizeof(buffer_in.header);
            if(!process_input())
                return -1;

            if(buffer_in_read_cursor < buffer_in_write_cursor) {
                log("session.c: read underrun (%d bytes remaining)",
                    buffer_in_write_cursor - buffer_in_read_cursor);
            }

            in_packet_reset();
        }
    }

    return consumed;
}

static void in_packet_chunk(void *ptr, int length)
{
    if(buffer_in_read_cursor + length > buffer_in_write_cursor) {
        log("session.c: read overrun while trying to read %d bytes"
            " (%d remaining)",
            length, buffer_in_write_cursor - buffer_in_read_cursor);
    }

    if(ptr != NULL)
        memcpy(ptr, &buffer_in.data[buffer_in_read_cursor], length);
    buffer_in_read_cursor += length;
}

static int8_t in_packet_int8()
{
    int8_t result;
    in_packet_chunk(&result, sizeof(result));
    return result;
}

static int32_t in_packet_int32()
{
    int32_t result;
    in_packet_chunk(&result, sizeof(result));
    return result;
}

static const void *in_packet_bytes(int *length)
{
    *length = in_packet_int32();
    const void *ptr = &buffer_in.data[buffer_in_read_cursor];
    in_packet_chunk(NULL, *length);
    return ptr;
}

static const char *in_packet_string()
{
    int length;
    const char *string = in_packet_bytes(&length);
    if(string[length] != 0) {
        log("session.c: string is not zero-terminated");
        return "";
    }
    return string;
}

// ============================= Writer interface =============================

static union {
    char data[BUFFER_OUT_SIZE];
    struct {
        int32_t sync;
        int32_t length;
        int8_t  type;
    } __attribute__((packed)) header;
} buffer_out;

static int buffer_out_read_cursor, buffer_out_write_cursor;

static void out_packet_reset()
{
    buffer_out_read_cursor  = 0;
    buffer_out_write_cursor = 0;
}

static int out_packet_available()
{
    return buffer_out_write_cursor == 0;
}

static void out_packet_extract(void **data, int *length)
{
    if(buffer_out_write_cursor > 0 &&
       buffer_out.header.length > 0) {
        *data   = &buffer_out.data[buffer_out_read_cursor];
        *length = buffer_out_write_cursor - buffer_out_read_cursor;
    } else {
        *length = 0;
    }
}

static void out_packet_advance(int length)
{
    if(buffer_out_read_cursor + length > buffer_out_write_cursor) {
        log("session.c: write underrun while trying to acknowledge %d bytes"
            " (%d remaining)",
            length, buffer_out_write_cursor - buffer_out_read_cursor);
        return;
    }

    buffer_out_read_cursor += length;
    if(buffer_out_read_cursor == buffer_out_write_cursor)
        out_packet_reset();
}

static int out_packet_chunk(const void *ptr, int length)
{
    if(buffer_out_write_cursor + length > BUFFER_OUT_SIZE) {
        log("session.c: write overrun while trying to write %d bytes"
            " (%d remaining)",
            length, BUFFER_OUT_SIZE - buffer_out_write_cursor);
        return 0;
    }

    memcpy(&buffer_out.data[buffer_out_write_cursor], ptr, length);
    buffer_out_write_cursor += length;
    return 1;
}

static void out_packet_start(int type)
{
    buffer_out.header.sync   = 0x5a5a5a5a;
    buffer_out.header.type   = type;
    buffer_out.header.length = 0;
    buffer_out_write_cursor  = sizeof(buffer_out.header);
}

static void out_packet_finish()
{
    buffer_out.header.length = buffer_out_write_cursor;
}

static void out_packet_empty(int type)
{
    out_packet_start(type);
    out_packet_finish();
}

static int out_packet_int8(int8_t value)
{
    return out_packet_chunk(&value, sizeof(value));
}

static int out_packet_int32(int32_t value)
{
    return out_packet_chunk(&value, sizeof(value));
}

static int out_packet_int64(int64_t value)
{
    return out_packet_chunk(&value, sizeof(value));
}

static int out_packet_float64(double value)
{
    return out_packet_chunk(&value, sizeof(value));
}

static int out_packet_bytes(const void *ptr, int length)
{
    return out_packet_int32(length) &&
           out_packet_chunk(ptr, length);
}

static int out_packet_string(const char *string)
{
    return out_packet_bytes(string, strlen(string) + 1);
}

// =============================== API handling ===============================

static int user_kernel_state;

enum {
    USER_KERNEL_NONE = 0,
    USER_KERNEL_LOADED,
    USER_KERNEL_RUNNING,
    USER_KERNEL_WAIT_RPC /* < must come after _RUNNING */
};

void session_start(void)
{
    in_packet_reset();
    out_packet_reset();

    kloader_stop();
    now = -1;
    user_kernel_state = USER_KERNEL_NONE;
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

    REMOTEMSG_TYPE_LOAD_LIBRARY,
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

static int process_input(void)
{
    switch(buffer_in.header.type) {
        case REMOTEMSG_TYPE_IDENT_REQUEST:
            out_packet_start(REMOTEMSG_TYPE_IDENT_REPLY);
            out_packet_chunk("AROR", 4);
            out_packet_finish();
            break;

        case REMOTEMSG_TYPE_SWITCH_CLOCK: {
            int clk = in_packet_int8();

            if(user_kernel_state >= USER_KERNEL_RUNNING) {
                log("Attempted to switch RTIO clock while kernel running");
                out_packet_empty(REMOTEMSG_TYPE_CLOCK_SWITCH_FAILED);
                break;
            }

            if(rtiocrg_switch_clock(clk))
                out_packet_empty(REMOTEMSG_TYPE_CLOCK_SWITCH_COMPLETED);
            else
                out_packet_empty(REMOTEMSG_TYPE_CLOCK_SWITCH_FAILED);
            break;
        }

        case REMOTEMSG_TYPE_LOG_REQUEST:
#if (LOG_BUFFER_SIZE + 9) > BUFFER_OUT_SIZE
#error Output buffer cannot hold the log buffer
#endif
            out_packet_start(REMOTEMSG_TYPE_LOG_REPLY);
            log_get(&buffer_out.data[buffer_out_write_cursor]);
            buffer_out_write_cursor += LOG_BUFFER_SIZE;
            out_packet_finish();
            break;

        case REMOTEMSG_TYPE_FLASH_READ_REQUEST: {
#if SPIFLASH_SECTOR_SIZE - 4 > BUFFER_OUT_SIZE - 9
#error Output buffer cannot hold the flash storage data
#endif
            const char *key = in_packet_string();
            int value_length;

            out_packet_start(REMOTEMSG_TYPE_FLASH_READ_REPLY);
            value_length = fs_read(key, &buffer_out.data[buffer_out_write_cursor],
                                   sizeof(buffer_out.data) - buffer_out_write_cursor, NULL);
            buffer_out_write_cursor += value_length;
            out_packet_finish();
            break;
        }

        case REMOTEMSG_TYPE_FLASH_WRITE_REQUEST: {
#if SPIFLASH_SECTOR_SIZE - 4 > BUFFER_IN_SIZE - 9
#error Input buffer cannot hold the flash storage data
#endif
            const char *key, *value;
            int value_length;
            key   = in_packet_string();
            value = in_packet_bytes(&value_length);

            if(fs_write(key, value, value_length))
                out_packet_empty(REMOTEMSG_TYPE_FLASH_OK_REPLY);
            else
                out_packet_empty(REMOTEMSG_TYPE_FLASH_ERROR_REPLY);
            break;
        }

        case REMOTEMSG_TYPE_FLASH_ERASE_REQUEST:
            fs_erase();
            out_packet_empty(REMOTEMSG_TYPE_FLASH_OK_REPLY);
            break;

        case REMOTEMSG_TYPE_FLASH_REMOVE_REQUEST: {
            const char *key = in_packet_string();

            fs_remove(key);
            out_packet_empty(REMOTEMSG_TYPE_FLASH_OK_REPLY);
            break;
        }

        case REMOTEMSG_TYPE_LOAD_LIBRARY: {
            const void *kernel = &buffer_in.data[buffer_in_read_cursor];
            buffer_in_read_cursor = buffer_in_write_cursor;

            if(user_kernel_state >= USER_KERNEL_RUNNING) {
                log("Attempted to load new kernel library while already running");
                out_packet_empty(REMOTEMSG_TYPE_LOAD_FAILED);
                break;
            }

            if(kloader_load_library(kernel)) {
                out_packet_empty(REMOTEMSG_TYPE_LOAD_COMPLETED);
                user_kernel_state = USER_KERNEL_LOADED;
            } else {
                out_packet_empty(REMOTEMSG_TYPE_LOAD_FAILED);
            }
            break;
        }

        case REMOTEMSG_TYPE_RUN_KERNEL:
            if(user_kernel_state != USER_KERNEL_LOADED) {
                log("Attempted to run kernel while not in the LOADED state");
                out_packet_empty(REMOTEMSG_TYPE_KERNEL_STARTUP_FAILED);
                break;
            }

            watchdog_init();
            kloader_start_kernel();

            user_kernel_state = USER_KERNEL_RUNNING;
            break;

        case REMOTEMSG_TYPE_RPC_REPLY: {
            struct msg_rpc_reply reply;

            if(user_kernel_state != USER_KERNEL_WAIT_RPC) {
                log("Unsolicited RPC reply");
                return 0; // restart session
            }

            reply.type = MESSAGE_TYPE_RPC_REPLY;
            // FIXME memcpy(&reply.eid, &buffer_in[9], 4);
            // memcpy(&reply.retval, &buffer_in[13], 4);
            mailbox_send_and_wait(&reply);
            user_kernel_state = USER_KERNEL_RUNNING;
            break;
        }

        default:
            return 0;
    }

    return 1;
}

static int send_rpc_value(const char **tag, void *value)
{
    out_packet_int8(**tag);

    int size = 0;
    switch(**tag) {
        case 0: // last tag
        case 'n': // None
            break;

        case 'b': // bool
            size = 1;
            out_packet_chunk(value, size);
            break;

        case 'i': // int(width=32)
            size = 4;
            out_packet_chunk(value, size);
            break;

        case 'I': // int(width=64)
        case 'f': // float
            size = 8;
            out_packet_chunk(value, size);
            break;

        case 'F': // Fraction
            size = 16;
            out_packet_chunk(value, size);
            break;

        case 'l': { // list(elt='a)
            size = sizeof(void*);

            struct { uint32_t length; void *elements; } *list = value;
            void *element = list->elements;

            const char *tag_copy = *tag + 1;
            for(int i = 0; i < list->length; i++) {
                int element_size = send_rpc_value(&tag_copy, element);
                if(element_size < 0)
                    return -1;
                element = (void*)((intptr_t)element + element_size);
            }
            *tag = tag_copy;
            break;
        }

        default:
            return -1;
    }

    (*tag)++;
    return size;
}

static int send_rpc_request(int service, va_list args)
{
    out_packet_start(REMOTEMSG_TYPE_RPC_REQUEST);
    out_packet_int32(service);

    const char *tag = va_arg(args, const char*);
    while(*tag) {
        void *value = va_arg(args, void*);
        if(!kloader_validate_kpointer(value))
            return 0;
        if(send_rpc_value(&tag, &value) < 0)
            return 0;
    }

    out_packet_finish();
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
            out_packet_empty(REMOTEMSG_TYPE_KERNEL_FINISHED);

            kloader_stop();
            user_kernel_state = USER_KERNEL_LOADED;
            mailbox_acknowledge();
            break;

        case MESSAGE_TYPE_EXCEPTION: {
            struct msg_exception *msg = (struct msg_exception *)umsg;

            out_packet_empty(REMOTEMSG_TYPE_KERNEL_EXCEPTION);
            // memcpy(&buffer_out[9], &msg->eid, 4);
            // memcpy(&buffer_out[13], msg->eparams, 3*8);
            // submit_output(9+4+3*8);

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

            if(!send_rpc_request(msg->rpc_num, msg->args)) {
                log("Failed to send RPC request");
                return 0;
            }

            user_kernel_state = USER_KERNEL_WAIT_RPC;
            mailbox_acknowledge();
            break;
        }

        default:
            log("Received invalid message type %d from kernel CPU",
                umsg->type);
            return 0;
    }
    return 1;
}

/* Returns amount of bytes consumed on success.
 * Returns -1 in case of irrecoverable error
 * (the session must be dropped and session_end called).
 * Returns -2 if the host has requested session reset.
 */
int session_input(void *data, int length)
{
    return in_packet_fill((uint8_t*)data, length);
}

/* *length is set to -1 in case of irrecoverable error
 * (the session must be dropped and session_end called)
 */
void session_poll(void **data, int *length)
{
    if(user_kernel_state == USER_KERNEL_RUNNING) {
        if(watchdog_expired()) {
            log("Watchdog expired");
            *length = -1;
            return;
        }
        if(!rtiocrg_check()) {
            log("RTIO clock failure");
            *length = -1;
            return;
        }
    }

    /* If the output buffer is available,
     * check if the kernel CPU has something to transmit.
     */
    if(out_packet_available()) {
        struct msg_base *umsg = mailbox_receive();
        if(umsg) {
            if(!process_kmsg(umsg)) {
                *length = -1;
                return;
            }
        }
    }

    out_packet_extract(data, length);
}

void session_ack(int length)
{
    out_packet_advance(length);
}
