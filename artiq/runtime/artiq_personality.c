#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <unwind.h>
#include "artiq_personality.h"

/* Logging */

#ifndef NDEBUG
#define EH_LOG0(fmt)     fprintf(stderr, "%s: " fmt "\n", __func__)
#define EH_LOG(fmt, ...) fprintf(stderr, "%s: " fmt "\n", __func__, __VA_ARGS__)
#else
#define EH_LOG0(fmt)
#define EH_LOG(fmt, ...)
#endif

#define EH_FAIL(err) \
  do { \
    fprintf(stderr, "%s fatal: %s\n", __func__, err); \
    abort(); \
  } while(0)

#define EH_ASSERT(expr) \
  if(!(expr)) EH_FAIL(#expr)

/* DWARF format handling */

enum {
    DW_EH_PE_absptr   = 0x00,
    DW_EH_PE_uleb128  = 0x01,
    DW_EH_PE_udata2   = 0x02,
    DW_EH_PE_udata4   = 0x03,
    DW_EH_PE_udata8   = 0x04,
    DW_EH_PE_sleb128  = 0x09,
    DW_EH_PE_sdata2   = 0x0A,
    DW_EH_PE_sdata4   = 0x0B,
    DW_EH_PE_sdata8   = 0x0C,
    DW_EH_PE_pcrel    = 0x10,
    DW_EH_PE_textrel  = 0x20,
    DW_EH_PE_datarel  = 0x30,
    DW_EH_PE_funcrel  = 0x40,
    DW_EH_PE_aligned  = 0x50,
    DW_EH_PE_indirect = 0x80,
    DW_EH_PE_omit     = 0xFF
};

// Read a uleb128 encoded value and advance pointer
// See Variable Length Data in: http://dwarfstd.org/Dwarf3.pdf
static uintptr_t readULEB128(const uint8_t **data) {
  uintptr_t result = 0;
  uintptr_t shift = 0;
  unsigned char byte;
  const uint8_t *p = *data;

  do {
    byte = *p++;
    result |= (byte & 0x7f) << shift;
    shift += 7;
  }
  while (byte & 0x80);

  *data = p;

  return result;
}

// Read a sleb128 encoded value and advance pointer
// See Variable Length Data in: http://dwarfstd.org/Dwarf3.pdf
static uintptr_t readSLEB128(const uint8_t **data) {
  uintptr_t result = 0;
  uintptr_t shift = 0;
  unsigned char byte;
  const uint8_t *p = *data;

  do {
    byte = *p++;
    result |= (byte & 0x7f) << shift;
    shift += 7;
  }
  while (byte & 0x80);

  *data = p;

  if ((byte & 0x40) && (shift < (sizeof(result) << 3))) {
    result |= (~0 << shift);
  }

  return result;
}

static unsigned getEncodingSize(uint8_t Encoding) {
  if (Encoding == DW_EH_PE_omit)
    return 0;

  switch (Encoding & 0x0F) {
  case DW_EH_PE_absptr:
    return sizeof(uintptr_t);
  case DW_EH_PE_udata2:
    return sizeof(uint16_t);
  case DW_EH_PE_udata4:
    return sizeof(uint32_t);
  case DW_EH_PE_udata8:
    return sizeof(uint64_t);
  case DW_EH_PE_sdata2:
    return sizeof(int16_t);
  case DW_EH_PE_sdata4:
    return sizeof(int32_t);
  case DW_EH_PE_sdata8:
    return sizeof(int64_t);
  default:
    // not supported
    abort();
  }
}

// Read a pointer encoded value and advance pointer
// See Variable Length Data in: http://dwarfstd.org/Dwarf3.pdf
static uintptr_t readEncodedPointer(const uint8_t **data, uint8_t encoding) {
  uintptr_t result = 0;
  const uint8_t *p = *data;

  if (encoding == DW_EH_PE_omit)
    return(result);

  // first get value
  switch (encoding & 0x0F) {
    case DW_EH_PE_absptr:
      memcpy(&result, p, sizeof(uintptr_t));
      p += sizeof(uintptr_t);
      break;
    case DW_EH_PE_uleb128:
      result = readULEB128(&p);
      break;
      // Note: This case has not been tested
    case DW_EH_PE_sleb128:
      result = readSLEB128(&p);
      break;
    case DW_EH_PE_udata2:
      {
        uint16_t valu16;
        memcpy(&valu16, p, sizeof(uint16_t));
        result = valu16;
      }
      p += sizeof(uint16_t);
      break;
    case DW_EH_PE_udata4:
      {
        uint32_t valu32;
        memcpy(&valu32, p, sizeof(uint32_t));
        result = valu32;
      }
      p += sizeof(uint32_t);
      break;
    case DW_EH_PE_udata8:
      {
        uint64_t valu64;
        memcpy(&valu64, p, sizeof(uint64_t));
        result = valu64;
      }
      p += sizeof(uint64_t);
      break;
    case DW_EH_PE_sdata2:
      {
        int16_t val16;
        memcpy(&val16, p, sizeof(int16_t));
        result = val16;
      }
      p += sizeof(int16_t);
      break;
    case DW_EH_PE_sdata4:
      {
        int32_t val32;
        memcpy(&val32, p, sizeof(int32_t));
        result = val32;
      }
      p += sizeof(int32_t);
      break;
    case DW_EH_PE_sdata8:
      {
        int64_t val64;
        memcpy(&val64, p, sizeof(int64_t));
        result = val64;
      }
      p += sizeof(int64_t);
      break;
    default:
      // not supported
      abort();
      break;
  }

  // then add relative offset
  switch (encoding & 0x70) {
    case DW_EH_PE_absptr:
      // do nothing
      break;
    case DW_EH_PE_pcrel:
      result += (uintptr_t)(*data);
      break;
    case DW_EH_PE_textrel:
    case DW_EH_PE_datarel:
    case DW_EH_PE_funcrel:
    case DW_EH_PE_aligned:
    default:
      // not supported
      abort();
      break;
  }

  // then apply indirection
  if (encoding & DW_EH_PE_indirect) {
    result = *((uintptr_t*)result);
  }

  *data = p;

  return result;
}


/* Raising */

#define ARTIQ_EXCEPTION_CLASS 0x4152545141525451LL // 'ARTQARTQ'

static void __artiq_cleanup(_Unwind_Reason_Code reason, struct _Unwind_Exception *exc);
static _Unwind_Reason_Code __artiq_uncaught_exception(
        int version, _Unwind_Action actions, uint64_t exceptionClass,
        struct _Unwind_Exception *exceptionObject, struct _Unwind_Context *context,
        void *stop_parameter);

struct artiq_raised_exception {
  struct _Unwind_Exception unwind;
  struct artiq_exception artiq;
  int handled;
  struct artiq_backtrace_item backtrace[1024];
  size_t backtrace_size;
};

static struct artiq_raised_exception inflight;

void __artiq_raise(struct artiq_exception *artiq_exn) {
  EH_LOG("===> raise (name=%s, msg=%s, params=[%lld,%lld,%lld])",
         artiq_exn->name, artiq_exn->message,
         (long long int)artiq_exn->param[0],
         (long long int)artiq_exn->param[1],
         (long long int)artiq_exn->param[2]);

  memmove(&inflight.artiq, artiq_exn, sizeof(struct artiq_exception));
  inflight.unwind.exception_class = ARTIQ_EXCEPTION_CLASS;
  inflight.unwind.exception_cleanup = &__artiq_cleanup;
  inflight.handled = 0;
  inflight.backtrace_size = 0;

  _Unwind_Reason_Code result = _Unwind_RaiseException(&inflight.unwind);
  EH_ASSERT((result == _URC_END_OF_STACK) &&
            "Unexpected error during unwinding");

  // If we're here, there are no handlers, only cleanups.
  // Force unwinding anyway; we shall stop at nothing except the end of stack.
  result = _Unwind_ForcedUnwind(&inflight.unwind, &__artiq_uncaught_exception,
                                NULL);
  EH_FAIL("_Unwind_ForcedUnwind should not return");
}

void __artiq_reraise() {
  if(inflight.handled) {
    EH_LOG0("===> reraise");
    __artiq_raise(&inflight.artiq);
  } else {
    EH_LOG0("===> resume");
    EH_ASSERT((inflight.artiq.typeinfo != 0) &&
              "Need an exception to reraise");
    _Unwind_Resume(&inflight.unwind);
    abort();
  }
}

/* Unwinding */

// The code below does not refer to the `inflight` global.

static void __artiq_cleanup(_Unwind_Reason_Code reason, struct _Unwind_Exception *exc) {
  EH_LOG0("===> cleanup");
  struct artiq_raised_exception *inflight = (struct artiq_raised_exception*) exc;
  // The in-flight exception is statically allocated, so we don't need to free it.
  // But, we clear it to mark it as processed.
  memset(&inflight->artiq, 0, sizeof(struct artiq_exception));
}

static _Unwind_Reason_Code __artiq_uncaught_exception(
        int version, _Unwind_Action actions, uint64_t exceptionClass,
        struct _Unwind_Exception *exceptionObject, struct _Unwind_Context *context,
        void *stop_parameter) {
  struct artiq_raised_exception *inflight =
          (struct artiq_raised_exception*)exceptionObject;
  EH_ASSERT(inflight->backtrace_size <
            sizeof(inflight->backtrace) / sizeof(inflight->backtrace[0]) &&
            "Out of space for backtrace");

  uintptr_t pc = _Unwind_GetIP(context);
  uintptr_t funcStart = _Unwind_GetRegionStart(context);
  uintptr_t pcOffset = pc - funcStart;
  EH_LOG("===> uncaught (pc=%p+%p)", (void*)funcStart, (void*)pcOffset);

  inflight->backtrace[inflight->backtrace_size].function = funcStart;
  inflight->backtrace[inflight->backtrace_size].offset = pcOffset;
  ++inflight->backtrace_size;

  if(actions & _UA_END_OF_STACK) {
    EH_LOG0("end of stack");
    __artiq_terminate(&inflight->artiq, inflight->backtrace, inflight->backtrace_size);
  } else {
    EH_LOG0("continue");
    return _URC_NO_REASON;
  }
}

_Unwind_Reason_Code __artiq_personality(
        int version, _Unwind_Action actions, uint64_t exceptionClass,
        struct _Unwind_Exception *exceptionObject, struct _Unwind_Context *context);
_Unwind_Reason_Code __artiq_personality(
        int version, _Unwind_Action actions, uint64_t exceptionClass,
        struct _Unwind_Exception *exceptionObject, struct _Unwind_Context *context) {
  EH_LOG("===> entry (actions =%s%s%s%s; class=%08lx; object=%p, context=%p)",
         (actions & _UA_SEARCH_PHASE ? " search" : ""),
         (actions & _UA_CLEANUP_PHASE ? " cleanup" : ""),
         (actions & _UA_HANDLER_FRAME ? " handler" : ""),
         (actions & _UA_FORCE_UNWIND ? " force-unwind" : ""),
         exceptionClass, exceptionObject, context);
  EH_ASSERT((exceptionClass == ARTIQ_EXCEPTION_CLASS) &&
            "Foreign exceptions are not supported");

  struct artiq_raised_exception *inflight =
          (struct artiq_raised_exception*)exceptionObject;
  EH_LOG("=> exception name=%s",
         inflight->artiq.name);

  // Get a pointer to LSDA. If there's no LSDA, this function doesn't
  // actually handle any exceptions.
  const uint8_t *lsda = (const uint8_t*) _Unwind_GetLanguageSpecificData(context);
  if(lsda == NULL)
    return _URC_CONTINUE_UNWIND;

  EH_LOG("lsda=%p", lsda);

  // Get the current instruction pointer and offset it before next
  // instruction in the current frame which threw the exception.
  uintptr_t pc = _Unwind_GetIP(context) - 1;

  // Get beginning of the current frame's code.
  uintptr_t funcStart = _Unwind_GetRegionStart(context);
  uintptr_t pcOffset = pc - funcStart;

  EH_LOG("=> pc=%p (%p+%p)", (void*)pc, (void*)funcStart, (void*)pcOffset);

  // Parse LSDA header.
  uint8_t lpStartEncoding = *lsda++;
  if (lpStartEncoding != DW_EH_PE_omit) {
    readEncodedPointer(&lsda, lpStartEncoding);
  }

  uint8_t ttypeEncoding = *lsda++;
  const uint8_t *classInfo = NULL;
  if (ttypeEncoding != DW_EH_PE_omit) {
    // Calculate type info locations in emitted dwarf code which
    // were flagged by type info arguments to llvm.eh.selector
    // intrinsic
    uintptr_t classInfoOffset = readULEB128(&lsda);
    classInfo = lsda + classInfoOffset;
    EH_LOG("classInfo=%p", classInfo);
  }

  // Walk call-site table looking for range that includes current PC.
  uint8_t callSiteEncoding = *lsda++;
  uint32_t callSiteTableLength = readULEB128(&lsda);
  const uint8_t *callSiteTableStart = lsda;
  const uint8_t *callSiteTableEnd = callSiteTableStart + callSiteTableLength;
  const uint8_t *actionTableStart = callSiteTableEnd;
  const uint8_t *callSitePtr = callSiteTableStart;

  while(callSitePtr < callSiteTableEnd) {
    uintptr_t start = readEncodedPointer(&callSitePtr,
                                         callSiteEncoding);
    uintptr_t length = readEncodedPointer(&callSitePtr,
                                          callSiteEncoding);
    uintptr_t landingPad = readEncodedPointer(&callSitePtr,
                                              callSiteEncoding);
    uintptr_t actionValue = readULEB128(&callSitePtr);

    EH_LOG("call site (start=+%p, len=%d, landingPad=+%p, actionValue=%d)",
           (void*)start, (int)length, (void*)landingPad, (int)actionValue);

    if(landingPad == 0) {
      EH_LOG0("no landing pad, skipping");
      continue;
    }

    if((start <= pcOffset) && (pcOffset < (start + length))) {
      EH_LOG0("=> call site matches pc");

      int exceptionMatched = 0;
      if(actionValue) {
        const uint8_t *actionEntry = actionTableStart + (actionValue - 1);
        EH_LOG("actionEntry=%p", actionEntry);

        for(;;) {
          // Each emitted DWARF action corresponds to a 2 tuple of
          // type info address offset, and action offset to the next
          // emitted action.
          intptr_t typeInfoOffset = readSLEB128(&actionEntry);
          const uint8_t *tempActionEntry = actionEntry;
          intptr_t actionOffset = readSLEB128(&tempActionEntry);
          EH_LOG("typeInfoOffset=%p actionOffset=%p",
                 (void*)typeInfoOffset, (void*)actionOffset);
          EH_ASSERT((typeInfoOffset >= 0) && "Filter clauses are not supported");

          if(typeInfoOffset > 0) {
            unsigned encodingSize = getEncodingSize(ttypeEncoding);
            const uint8_t *typeInfoPtrPtr = classInfo - typeInfoOffset * encodingSize;
            uintptr_t typeInfoPtr = readEncodedPointer(&typeInfoPtrPtr, ttypeEncoding);
            EH_LOG("encodingSize=%u typeInfoPtrPtr=%p typeInfoPtr=%p",
                   encodingSize, typeInfoPtrPtr, (void*)typeInfoPtr);
            EH_LOG("typeInfo=%s", (char*)typeInfoPtr);

            if(typeInfoPtr == 0 || !strcmp(inflight->artiq.typeinfo, typeInfoPtr)) {
              EH_LOG0("matching action found");
              exceptionMatched = 1;
              break;
            }
          }

          if (!actionOffset)
            break;

          actionEntry += actionOffset;
        }
      }

      if(!(actions & _UA_SEARCH_PHASE)) {
        EH_LOG0("=> jumping to landing pad");

        if(actions & _UA_HANDLER_FRAME)
          inflight->handled = 1;

        _Unwind_SetGR(context, __builtin_eh_return_data_regno(0),
                      (uintptr_t)exceptionObject);
        _Unwind_SetGR(context, __builtin_eh_return_data_regno(1),
                      (uintptr_t)&inflight->artiq);
        _Unwind_SetIP(context, funcStart + landingPad);

        return _URC_INSTALL_CONTEXT;
      } else if(exceptionMatched) {
        EH_LOG0("=> handler found");

        return _URC_HANDLER_FOUND;
      } else {
        EH_LOG0("=> handler not found");

        return _URC_CONTINUE_UNWIND;
      }
    }
  }

  return _URC_CONTINUE_UNWIND;
}
