#include <string.h>
#include <stdio.h>
#include <stdarg.h>
#include <id.h>

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

// 2.5MiB in payload + 1KiB for headers.
// We need more than 1MiB to send a 1MiB list due to tags;
// about 5/4MiB for an 1MiB int32 list, 9/8MiB for an 1MiB int64 list.
#define BUFFER_SIZE (2560*1024 + 1024)
#define BUFFER_IN_SIZE  BUFFER_SIZE
#define BUFFER_OUT_SIZE BUFFER_SIZE

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
                core_log("session.c: read underrun (%d bytes remaining)\n",
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
        core_log("session.c: read overrun while trying to read %d bytes"
                 " (%d remaining)\n",
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

static int64_t in_packet_int64()
{
    int64_t result;
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
    if(string[length - 1] != 0) {
        core_log("session.c: string is not zero-terminated\n");
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

static int buffer_out_read_cursor, buffer_out_sent_cursor, buffer_out_write_cursor;

static void out_packet_reset()
{
    buffer_out_read_cursor  = 0;
    buffer_out_write_cursor = 0;
    buffer_out_sent_cursor  = 0;
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

static void out_packet_advance_consumed(int length)
{
    if(buffer_out_read_cursor + length > buffer_out_write_cursor) {
        core_log("session.c: write underrun (consume) while trying to"
                 " acknowledge %d bytes (%d remaining)\n",
                 length, buffer_out_write_cursor - buffer_out_read_cursor);
        return;
    }

    buffer_out_read_cursor += length;
}

static void out_packet_advance_sent(int length)
{
    if(buffer_out_sent_cursor + length > buffer_out_write_cursor) {
        core_log("session.c: write underrun (send) while trying to"
                 " acknowledge %d bytes (%d remaining)\n",
                 length, buffer_out_write_cursor - buffer_out_sent_cursor);
        return;
    }

    buffer_out_sent_cursor += length;
    if(buffer_out_sent_cursor == buffer_out_write_cursor)
        out_packet_reset();
}

static int out_packet_chunk(const void *ptr, int length)
{
    if(buffer_out_write_cursor + length > BUFFER_OUT_SIZE) {
        core_log("session.c: write overrun while trying to write %d bytes"
                 " (%d remaining)\n",
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

void session_startup_kernel(void)
{
    struct msg_base *umsg;

    watchdog_init();
    if(!kloader_start_startup_kernel())
        return;

    core_log("Startup kernel started\n");
    while(1) {
        kloader_service_essential_kmsg();

        umsg = mailbox_receive();
        if(umsg) {
            if(!kloader_validate_kpointer(umsg))
                break;
            if(kloader_is_essential_kmsg(umsg->type))
                continue;
            if(umsg->type == MESSAGE_TYPE_FINISHED)
                break;
            else if(umsg->type == MESSAGE_TYPE_EXCEPTION) {
                core_log("WARNING: startup kernel ended with exception\n");
                break;
            } else {
                core_log("ERROR: received invalid message type from kernel CPU\n");
                break;
            }
        }

        if(watchdog_expired()) {
            core_log("WARNING: watchdog expired in startup kernel\n");
            break;
        }
    }
    kloader_stop();
    core_log("Startup kernel terminated\n");
}

void session_start(void)
{
    in_packet_reset();
    out_packet_reset();

    kloader_stop();
    user_kernel_state = USER_KERNEL_NONE;
}

void session_end(void)
{
    kloader_stop();
    watchdog_init();
    kloader_start_idle_kernel();
}

/* host to device */
enum {
    REMOTEMSG_TYPE_LOG_REQUEST = 1,
    REMOTEMSG_TYPE_LOG_CLEAR,

    REMOTEMSG_TYPE_IDENT_REQUEST,
    REMOTEMSG_TYPE_SWITCH_CLOCK,

    REMOTEMSG_TYPE_LOAD_LIBRARY,
    REMOTEMSG_TYPE_RUN_KERNEL,

    REMOTEMSG_TYPE_RPC_REPLY,
    REMOTEMSG_TYPE_RPC_EXCEPTION,

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
    REMOTEMSG_TYPE_FLASH_ERROR_REPLY,

    REMOTEMSG_TYPE_WATCHDOG_EXPIRED,
    REMOTEMSG_TYPE_CLOCK_FAILURE,
};

static int receive_rpc_value(const char **tag, void **slot);

static int process_input(void)
{
    switch(buffer_in.header.type) {
        case REMOTEMSG_TYPE_IDENT_REQUEST: {
            char version[IDENT_SIZE];

            get_ident(version);

            out_packet_start(REMOTEMSG_TYPE_IDENT_REPLY);
            out_packet_chunk("AROR", 4);
            out_packet_chunk(version, strlen(version));
            out_packet_finish();
            break;
        }

        case REMOTEMSG_TYPE_SWITCH_CLOCK: {
            int clk = in_packet_int8();

            if(user_kernel_state >= USER_KERNEL_RUNNING) {
                core_log("Attempted to switch RTIO clock while kernel running\n");
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
            core_log_get(&buffer_out.data[buffer_out_write_cursor]);
            buffer_out_write_cursor += LOG_BUFFER_SIZE;
            out_packet_finish();
            break;

        case REMOTEMSG_TYPE_LOG_CLEAR:
            core_log_clear();
            out_packet_empty(REMOTEMSG_TYPE_LOG_REPLY);
            break;

        case REMOTEMSG_TYPE_FLASH_READ_REQUEST: {
#if CONFIG_SPIFLASH_SECTOR_SIZE - 4 > BUFFER_OUT_SIZE - 9
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
#if CONFIG_SPIFLASH_SECTOR_SIZE - 4 > BUFFER_IN_SIZE - 9
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
                core_log("Attempted to load new kernel library while already running\n");
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
                core_log("Attempted to run kernel while not in the LOADED state\n");
                out_packet_empty(REMOTEMSG_TYPE_KERNEL_STARTUP_FAILED);
                break;
            }

            watchdog_init();
            kloader_start_kernel();

            user_kernel_state = USER_KERNEL_RUNNING;
            break;

        case REMOTEMSG_TYPE_RPC_REPLY: {
            struct msg_rpc_recv_request *request;
            struct msg_rpc_recv_reply reply;

            if(user_kernel_state != USER_KERNEL_WAIT_RPC) {
                core_log("Unsolicited RPC reply\n");
                return 0; // restart session
            }

            request = mailbox_wait_and_receive();
            if(request->type != MESSAGE_TYPE_RPC_RECV_REQUEST) {
                core_log("Expected MESSAGE_TYPE_RPC_RECV_REQUEST, got %d\n",
                         request->type);
                return 0; // restart session
            }

            const char *tag = in_packet_string();
            void *slot = request->slot;
            if(!receive_rpc_value(&tag, &slot)) {
                core_log("Failed to receive RPC reply\n");
                return 0; // restart session
            }

            reply.type = MESSAGE_TYPE_RPC_RECV_REPLY;
            reply.alloc_size = 0;
            reply.exception = NULL;
            mailbox_send_and_wait(&reply);

            user_kernel_state = USER_KERNEL_RUNNING;
            break;
        }

        case REMOTEMSG_TYPE_RPC_EXCEPTION: {
            struct msg_rpc_recv_request *request;
            struct msg_rpc_recv_reply reply;

            struct artiq_exception exception;
            exception.name     = in_packet_string();
            exception.message  = in_packet_string();
            exception.param[0] = in_packet_int64();
            exception.param[1] = in_packet_int64();
            exception.param[2] = in_packet_int64();
            exception.file     = in_packet_string();
            exception.line     = in_packet_int32();
            exception.column   = in_packet_int32();
            exception.function = in_packet_string();

            if(user_kernel_state != USER_KERNEL_WAIT_RPC) {
                core_log("Unsolicited RPC exception reply\n");
                return 0; // restart session
            }

            request = mailbox_wait_and_receive();
            if(request->type != MESSAGE_TYPE_RPC_RECV_REQUEST) {
                core_log("Expected MESSAGE_TYPE_RPC_RECV_REQUEST, got %d\n",
                    request->type);
                return 0; // restart session
            }

            reply.type = MESSAGE_TYPE_RPC_RECV_REPLY;
            reply.alloc_size = 0;
            reply.exception = &exception;
            mailbox_send_and_wait(&reply);

            user_kernel_state = USER_KERNEL_RUNNING;
            break;
        }

        default:
            core_log("Received invalid packet type %d from host\n",
                     buffer_in.header.type);
            return 0;
    }

    return 1;
}

// See comm_generic.py:_{send,receive}_rpc_value and llvm_ir_generator.py:_rpc_tag.
static void skip_rpc_value(const char **tag) {
    switch(*(*tag)++) {
        case 't': {
            int size = *(*tag)++;
            for(int i = 0; i < size; i++)
                skip_rpc_value(tag);
            break;
        }

        case 'l':
        case 'a':
            skip_rpc_value(tag);
            break;

        case 'r':
            skip_rpc_value(tag);
            break;
    }
}

static int sizeof_rpc_value(const char **tag)
{
    switch(*(*tag)++) {
        case 't': { // tuple
            int size = *(*tag)++;

            int32_t length = 0;
            for(int i = 0; i < size; i++)
                length += sizeof_rpc_value(tag);
            return length;
        }

        case 'n': // None
            return 0;

        case 'b': // bool
            return sizeof(int8_t);

        case 'i': // int(width=32)
            return sizeof(int32_t);

        case 'I': // int(width=64)
            return sizeof(int64_t);

        case 'f': // float
            return sizeof(double);

        case 'F': // Fraction
            return sizeof(struct { int64_t numerator, denominator; });

        case 's': // string
            return sizeof(char *);

        case 'l': // list(elt='a)
        case 'a': // array(elt='a)
            skip_rpc_value(tag);
            return sizeof(struct { int32_t length; struct {} *elements; });

        case 'r': // range(elt='a)
            return sizeof_rpc_value(tag) * 3;

        default:
            core_log("sizeof_rpc_value: unknown tag %02x\n", *((*tag) - 1));
            return 0;
    }
}

static void *alloc_rpc_value(int size)
{
    struct msg_rpc_recv_request *request;
    struct msg_rpc_recv_reply reply;

    reply.type = MESSAGE_TYPE_RPC_RECV_REPLY;
    reply.alloc_size = size;
    reply.exception = NULL;
    mailbox_send_and_wait(&reply);

    request = mailbox_wait_and_receive();
    if(request->type != MESSAGE_TYPE_RPC_RECV_REQUEST) {
        core_log("Expected MESSAGE_TYPE_RPC_RECV_REQUEST, got %d\n",
                 request->type);
        return NULL;
    }
    return request->slot;
}

static int receive_rpc_value(const char **tag, void **slot)
{
    switch(*(*tag)++) {
        case 't': { // tuple
            int size = *(*tag)++;

            for(int i = 0; i < size; i++) {
                if(!receive_rpc_value(tag, slot))
                    return 0;
            }
            break;
        }

        case 'n': // None
            break;

        case 'b': { // bool
            *((*(int8_t**)slot)++) = in_packet_int8();
            break;
        }

        case 'i': { // int(width=32)
            *((*(int32_t**)slot)++) = in_packet_int32();
            break;
        }

        case 'I': { // int(width=64)
            *((*(int64_t**)slot)++) = in_packet_int64();
            break;
        }

        case 'f': { // float
            *((*(int64_t**)slot)++) = in_packet_int64();
            break;
        }

        case 'F': { // Fraction
            struct { int64_t numerator, denominator; } *fraction = *slot;
            fraction->numerator = in_packet_int64();
            fraction->denominator = in_packet_int64();
            *slot = (void*)((intptr_t)(*slot) + sizeof(*fraction));
            break;
        }

        case 's': { // string
            const char *in_string = in_packet_string();
            char *out_string = alloc_rpc_value(strlen(in_string) + 1);
            memcpy(out_string, in_string, strlen(in_string) + 1);
            *((*(char***)slot)++) = out_string;
            break;
        }

        case 'l':   // list(elt='a)
        case 'a': { // array(elt='a)
            struct { int32_t length; struct {} *elements; } *list = *slot;
            list->length = in_packet_int32();

            const char *tag_copy = *tag;
            list->elements = alloc_rpc_value(sizeof_rpc_value(&tag_copy) * list->length);

            void *element = list->elements;
            for(int i = 0; i < list->length; i++) {
                const char *tag_copy = *tag;
                if(!receive_rpc_value(&tag_copy, &element))
                    return 0;
            }
            skip_rpc_value(tag);
            break;
        }

        case 'r': { // range(elt='a)
            const char *tag_copy;
            tag_copy = *tag;
            if(!receive_rpc_value(&tag_copy, slot)) // min
                return 0;
            tag_copy = *tag;
            if(!receive_rpc_value(&tag_copy, slot)) // max
                return 0;
            tag_copy = *tag;
            if(!receive_rpc_value(&tag_copy, slot)) // step
                return 0;
            *tag = tag_copy;
            break;
        }

        default:
            core_log("receive_rpc_value: unknown tag %02x\n", *((*tag) - 1));
            return 0;
    }

    return 1;
}

static int send_rpc_value(const char **tag, void **value)
{
    if(!out_packet_int8(**tag))
        return 0;

    switch(*(*tag)++) {
        case 't': { // tuple
            int size = *(*tag)++;
            if(!out_packet_int8(size))
                return 0;

            for(int i = 0; i < size; i++) {
                if(!send_rpc_value(tag, value))
                    return 0;
            }
            break;
        }

        case 'n': // None
            break;

        case 'b': { // bool
            return out_packet_int8(*((*(int8_t**)value)++));
        }

        case 'i': { // int(width=32)
            return out_packet_int32(*((*(int32_t**)value)++));
        }

        case 'I': { // int(width=64)
            return out_packet_int64(*((*(int64_t**)value)++));
        }

        case 'f': { // float
            return out_packet_float64(*((*(double**)value)++));
        }

        case 'F': { // Fraction
            struct { int64_t numerator, denominator; } *fraction = *value;
            if(!out_packet_int64(fraction->numerator))
                return 0;
            if(!out_packet_int64(fraction->denominator))
                return 0;
            *value = (void*)((intptr_t)(*value) + sizeof(*fraction));
            break;
        }

        case 's': { // string
            return out_packet_string(*((*(const char***)value)++));
        }

        case 'l':   // list(elt='a)
        case 'a': { // array(elt='a)
            struct { uint32_t length; struct {} *elements; } *list = *value;
            void *element = list->elements;

            if(!out_packet_int32(list->length))
                return 0;

            for(int i = 0; i < list->length; i++) {
                const char *tag_copy = *tag;
                if(!send_rpc_value(&tag_copy, &element)) {
                    core_log("failed to send list at element %d/%d\n", i, list->length);
                    return 0;
                }
            }
            skip_rpc_value(tag);

            *value = (void*)((intptr_t)(*value) + sizeof(*list));
            break;
        }

        case 'r': { // range(elt='a)
            const char *tag_copy;
            tag_copy = *tag;
            if(!send_rpc_value(&tag_copy, value)) // min
                return 0;
            tag_copy = *tag;
            if(!send_rpc_value(&tag_copy, value)) // max
                return 0;
            tag_copy = *tag;
            if(!send_rpc_value(&tag_copy, value)) // step
                return 0;
            *tag = tag_copy;
            break;
        }

        case 'k': { // keyword(value='a)
            struct { const char *name; struct {} contents; } *option = *value;
            void *contents = &option->contents;

            if(!out_packet_string(option->name))
                return 0;

            // keyword never appears in composite types, so we don't have
            // to accurately advance *value.
            return send_rpc_value(tag, &contents);
        }

        case 'O': { // host object
            struct { uint32_t id; } **object = *value;

            if(!out_packet_int32((*object)->id))
                return 0;

            *value = (void*)((intptr_t)(*value) + sizeof(*object));
            break;
        }

        default:
            core_log("send_rpc_value: unknown tag %02x\n", *((*tag) - 1));
            return 0;
    }

    return 1;
}

static int send_rpc_request(int service, const char *tag, void **data)
{
    out_packet_start(REMOTEMSG_TYPE_RPC_REQUEST);
    out_packet_int32(service);

    while(*tag != ':') {
        void *value = *data++;
        if(!kloader_validate_kpointer(value))
            return 0;
        if(!send_rpc_value(&tag, &value))
            return 0;
    }
    out_packet_int8(0);

    out_packet_string(tag + 1); // return tags
    out_packet_finish();
    return 1;
}

struct cache_row {
    struct cache_row *next;
    char *key;
    size_t length;
    int32_t *elements;
    int borrowed;
};

static struct cache_row *cache;

/* assumes output buffer is empty when called */
static int process_kmsg(struct msg_base *umsg)
{
    if(!kloader_validate_kpointer(umsg))
        return 0;
    if(kloader_is_essential_kmsg(umsg->type))
        return 1; /* handled elsewhere */
    if(user_kernel_state == USER_KERNEL_LOADED &&
       umsg->type == MESSAGE_TYPE_LOAD_REPLY) {
        // Kernel standing by.
        return 1;
    }
    if(user_kernel_state == USER_KERNEL_WAIT_RPC &&
       umsg->type == MESSAGE_TYPE_RPC_RECV_REQUEST) {
        // Handled and acknowledged when we receive
        // REMOTEMSG_TYPE_RPC_{EXCEPTION,REPLY}.
        return 1;
    }
    if(user_kernel_state != USER_KERNEL_RUNNING) {
        core_log("Received unexpected message from kernel CPU while not in running state\n");
        return 0;
    }

    switch(umsg->type) {
        case MESSAGE_TYPE_FINISHED:
            out_packet_empty(REMOTEMSG_TYPE_KERNEL_FINISHED);

            for(struct cache_row *iter = cache; iter; iter = iter->next)
                iter->borrowed = 0;

            kloader_stop();
            user_kernel_state = USER_KERNEL_LOADED;

            break;

        case MESSAGE_TYPE_EXCEPTION: {
            struct msg_exception *msg = (struct msg_exception *)umsg;

            out_packet_start(REMOTEMSG_TYPE_KERNEL_EXCEPTION);

            out_packet_string(msg->exception->name);
            out_packet_string(msg->exception->message);
            out_packet_int64(msg->exception->param[0]);
            out_packet_int64(msg->exception->param[1]);
            out_packet_int64(msg->exception->param[2]);

            out_packet_string(msg->exception->file);
            out_packet_int32(msg->exception->line);
            out_packet_int32(msg->exception->column);
            out_packet_string(msg->exception->function);

            out_packet_int32(msg->backtrace_size);
            for(int i = 0; i < msg->backtrace_size; i++) {
                out_packet_int32(msg->backtrace[i]);
            }

            out_packet_finish();

            kloader_stop();
            user_kernel_state = USER_KERNEL_LOADED;
            mailbox_acknowledge();
            break;
        }

        case MESSAGE_TYPE_RPC_SEND:
        case MESSAGE_TYPE_RPC_BATCH: {
            struct msg_rpc_send *msg = (struct msg_rpc_send *)umsg;

            if(!send_rpc_request(msg->service, msg->tag, msg->data)) {
                core_log("Failed to send RPC request (service %d, tag %s)\n",
                         msg->service, msg->tag);
                return 0; // restart session
            }

            if(msg->type == MESSAGE_TYPE_RPC_SEND)
                user_kernel_state = USER_KERNEL_WAIT_RPC;
            mailbox_acknowledge();
            break;
        }

        case MESSAGE_TYPE_CACHE_GET_REQUEST: {
            struct msg_cache_get_request *request = (struct msg_cache_get_request *)umsg;
            struct msg_cache_get_reply reply;

            reply.type = MESSAGE_TYPE_CACHE_GET_REPLY;
            reply.length = 0;
            reply.elements = NULL;

            for(struct cache_row *iter = cache; iter; iter = iter->next) {
                if(!strcmp(iter->key, request->key)) {
                    reply.length = iter->length;
                    reply.elements = iter->elements;
                    iter->borrowed = 1;
                    break;
                }
            }

            mailbox_send(&reply);
            break;
        }

        case MESSAGE_TYPE_CACHE_PUT_REQUEST: {
            struct msg_cache_put_request *request = (struct msg_cache_put_request *)umsg;
            struct msg_cache_put_reply reply;

            reply.type = MESSAGE_TYPE_CACHE_PUT_REPLY;

            struct cache_row *row = NULL;
            for(struct cache_row *iter = cache; iter; iter = iter->next) {
                if(!strcmp(iter->key, request->key)) {
                    row = iter;
                    break;
                }
            }

            if(!row) {
                row = calloc(1, sizeof(struct cache_row));
                row->key = calloc(strlen(request->key) + 1, 1);
                strcpy(row->key, request->key);
                row->next = cache;
                cache = row;
            }

            if(!row->borrowed) {
                row->length = request->length;
                if(row->length != 0) {
                    row->elements = calloc(row->length, sizeof(int32_t));
                    memcpy(row->elements, request->elements,
                           sizeof(int32_t) * row->length);
                } else {
                    free(row->elements);
                    row->elements = NULL;
                }

                reply.succeeded = 1;
            } else {
                reply.succeeded = 0;
            }

            mailbox_send(&reply);
            break;
        }

        default: {
            core_log("Received invalid message type %d from kernel CPU\n",
                     umsg->type);
            return 0;
        }
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
void session_poll(void **data, int *length, int *close_flag)
{
    *close_flag = 0;

    if(user_kernel_state == USER_KERNEL_RUNNING) {
        if(watchdog_expired()) {
            core_log("Watchdog expired\n");

            *close_flag = 1;
            out_packet_empty(REMOTEMSG_TYPE_WATCHDOG_EXPIRED);
        }
        if(!rtiocrg_check()) {
            core_log("RTIO clock failure\n");

            *close_flag = 1;
            out_packet_empty(REMOTEMSG_TYPE_CLOCK_FAILURE);
        }
    }

    if(!*close_flag) {
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
    }

    out_packet_extract(data, length);
}

void session_ack_consumed(int length)
{
    out_packet_advance_consumed(length);
}

void session_ack_sent(int length)
{
    out_packet_advance_sent(length);
}
