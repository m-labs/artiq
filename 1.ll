; ModuleID = '<string>'
source_filename = "<string>"
target datalayout = "e-m:e-p:32:32-i64:64-n32-S128"
target triple = "riscv32-unknown-linux"

<<<<<<< HEAD
%D.5 = type { %A.4**, i8** }
%A.4 = type { i32, { i8*, i32 }, { i8*, i32 } }

@S.nn = private unnamed_addr constant [3 x i8] c"n:n"
@S.ii = private unnamed_addr constant [3 x i8] c"ii:"
@S.i = private unnamed_addr constant [2 x i8] c"i:"
@S.in.1 = private unnamed_addr constant [3 x i8] c"i:n"
@typeinfo = local_unnamed_addr global [1 x %D.5*] zeroinitializer
=======
%D.59 = type { %A.58**, i8** }
%A.58 = type { i32, { i8*, i32 }, { i8*, i32 } }

@S.nn = private unnamed_addr constant [3 x i8] c"n:n"
<<<<<<< HEAD
@S.iI = private unnamed_addr constant [3 x i8] c"iI:"
@S.in.1 = private unnamed_addr constant [3 x i8] c"i:n"
=======
@S. = private unnamed_addr constant [1 x i8] c":"
>>>>>>> 76594e85a (don't waste time and bandwidth with returning Nones)
@now = external local_unnamed_addr global i64
@typeinfo = local_unnamed_addr global [1 x %D.59*] zeroinitializer
>>>>>>> ff18ac7b5 (don't waste time and bandwidth with returning Nones)

; Function Attrs: uwtable
define void @__modinit__(i8* nocapture readnone %.1) local_unnamed_addr #0 personality i32 (...)* @__artiq_personality !dbg !5 {
entry:
  %rpc.arg0 = alloca {}, align 8, !dbg !9
<<<<<<< HEAD
  call fastcc void @_Z42artiq_run_test_subkernel_opt.DMAPulses.runzz(), !dbg !10
=======
  call fastcc void @_Z38artiq_run_test_subkernel.DMAPulses.runzz(), !dbg !10
>>>>>>> ff18ac7b5 (don't waste time and bandwidth with returning Nones)
  %.3 = alloca { i8*, i32 }, align 8, !dbg !9
  %.3.repack = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.3, i32 0, i32 0, !dbg !9
  store i8* getelementptr inbounds ([3 x i8], [3 x i8]* @S.nn, i32 0, i32 0), i8** %.3.repack, align 8, !dbg !9
  %.3.repack1 = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.3, i32 0, i32 1, !dbg !9
  store i32 3, i32* %.3.repack1, align 4, !dbg !9
  %rpc.args = alloca i8*, align 4, !dbg !9
  %0 = bitcast i8** %rpc.args to {}**, !dbg !9
  store {}* %rpc.arg0, {}** %0, align 4, !dbg !9
  call void @rpc_send_async(i32 1, { i8*, i32 }* nonnull %.3, i8** nonnull %rpc.args), !dbg !9
  ret void, !dbg !9
}

declare i32 @__artiq_personality(...)

; Function Attrs: uwtable
<<<<<<< HEAD
define private fastcc void @_Z42artiq_run_test_subkernel_opt.DMAPulses.runzz() unnamed_addr #0 personality i32 (...)* @__artiq_personality !dbg !11 {
entry:
  %rpc.ret.alloc = alloca {}, align 8, !dbg !13
  call void @subkernel_load_run(i32 3, i1 true), !dbg !14
  %subkernel.stack = call i8* @llvm.stacksave(), !dbg !14
  %.12 = alloca { i8*, i32 }, align 8, !dbg !14
  %.12.repack = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.12, i32 0, i32 0, !dbg !14
  store i8* getelementptr inbounds ([3 x i8], [3 x i8]* @S.ii, i32 0, i32 0), i8** %.12.repack, align 8, !dbg !14
  %.12.repack1 = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.12, i32 0, i32 1, !dbg !14
  store i32 3, i32* %.12.repack1, align 4, !dbg !14
  %subkernel.args2 = alloca [2 x i8*], align 4, !dbg !14
  %subkernel.arg0 = alloca i32, align 4, !dbg !14
  %subkernel.args2.sub = getelementptr inbounds [2 x i8*], [2 x i8*]* %subkernel.args2, i32 0, i32 0
  store i32 184594432, i32* %subkernel.arg0, align 4, !dbg !14
  %0 = bitcast [2 x i8*]* %subkernel.args2 to i32**, !dbg !14
  store i32* %subkernel.arg0, i32** %0, align 4, !dbg !14
  %subkernel.arg1 = alloca i32, align 4, !dbg !14
  store i32 485, i32* %subkernel.arg1, align 4, !dbg !14
  %.20 = getelementptr inbounds [2 x i8*], [2 x i8*]* %subkernel.args2, i32 0, i32 1, !dbg !14
  %1 = bitcast i8** %.20 to i32**, !dbg !14
  store i32* %subkernel.arg1, i32** %1, align 4, !dbg !14
  call void @subkernel_send_message(i32 3, i8 2, { i8*, i32 }* nonnull %.12, i8** nonnull %subkernel.args2.sub), !dbg !14
  call void @llvm.stackrestore(i8* %subkernel.stack), !dbg !14
  %subkernel.await.message = call i8 @subkernel_await_message(i32 3, i64 10000, i8 1, i8 1), !dbg !15
  %subkernel.arg.stack = call i8* @llvm.stacksave(), !dbg !15
  %rpc.ret.alloc.subkernel.ret = alloca i32, align 4, !dbg !15
  %rpc.ret.ptr.subkernel.ret = bitcast i32* %rpc.ret.alloc.subkernel.ret to i8*, !dbg !15
  br label %rpc.head.subkernel.ret, !dbg !15

rpc.head.subkernel.ret:                           ; preds = %rpc.continue.subkernel.ret, %entry
  %rpc.ptr.subkernel.ret = phi i8* [ %rpc.ret.ptr.subkernel.ret, %entry ], [ %rpc.alloc.subkernel.ret, %rpc.continue.subkernel.ret ], !dbg !15
  %rpc.size.next.subkernel.ret = call i32 @rpc_recv(i8* %rpc.ptr.subkernel.ret), !dbg !15
  %rpc.done.subkernel.ret = icmp eq i32 %rpc.size.next.subkernel.ret, 0, !dbg !15
  br i1 %rpc.done.subkernel.ret, label %rpc.tail.subkernel.ret, label %rpc.continue.subkernel.ret, !dbg !15

rpc.continue.subkernel.ret:                       ; preds = %rpc.head.subkernel.ret
  %rpc.alloc.subkernel.ret = alloca i8, i32 %rpc.size.next.subkernel.ret, align 8, !dbg !15
  br label %rpc.head.subkernel.ret, !dbg !15

rpc.tail.subkernel.ret:                           ; preds = %rpc.head.subkernel.ret
  %rpc.ret.subkernel.ret = load i32, i32* %rpc.ret.alloc.subkernel.ret, align 4, !dbg !15
  call void @llvm.stackrestore(i8* %subkernel.arg.stack), !dbg !15
  call void @subkernel_await_finish(i32 3, i64 10000), !dbg !15
  %rpc.stack = call i8* @llvm.stacksave(), !dbg !13
  %.31 = alloca { i8*, i32 }, align 8, !dbg !13
  %.31.repack = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.31, i32 0, i32 0, !dbg !13
  store i8* getelementptr inbounds ([3 x i8], [3 x i8]* @S.in.1, i32 0, i32 0), i8** %.31.repack, align 8, !dbg !13
  %.31.repack3 = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.31, i32 0, i32 1, !dbg !13
  store i32 3, i32* %.31.repack3, align 4, !dbg !13
  %rpc.args = alloca i8*, align 4, !dbg !13
  %rpc.arg0 = alloca i32, align 4, !dbg !13
  store i32 %rpc.ret.subkernel.ret, i32* %rpc.arg0, align 4, !dbg !13
  %2 = bitcast i8** %rpc.args to i32**, !dbg !13
  store i32* %rpc.arg0, i32** %2, align 4, !dbg !13
  call void @rpc_send(i32 2, { i8*, i32 }* nonnull %.31, i8** nonnull %rpc.args), !dbg !13
  call void @llvm.stackrestore(i8* %rpc.stack), !dbg !13
  %rpc.ret.ptr = bitcast {}* %rpc.ret.alloc to i8*, !dbg !13
  br label %rpc.head, !dbg !13

rpc.head:                                         ; preds = %rpc.continue, %rpc.tail.subkernel.ret
  %rpc.ptr = phi i8* [ %rpc.ret.ptr, %rpc.tail.subkernel.ret ], [ %rpc.alloc, %rpc.continue ], !dbg !13
  %rpc.size.next = call i32 @rpc_recv(i8* %rpc.ptr), !dbg !13
  %rpc.done = icmp eq i32 %rpc.size.next, 0, !dbg !13
  br i1 %rpc.done, label %rpc.tail, label %rpc.continue, !dbg !13

rpc.continue:                                     ; preds = %rpc.head
  %rpc.alloc = alloca i8, i32 %rpc.size.next, align 8, !dbg !13
  br label %rpc.head, !dbg !13

rpc.tail:                                         ; preds = %rpc.head
  call void @llvm.stackrestore(i8* %rpc.stack), !dbg !13
  call void @subkernel_load_run(i32 3, i1 true), !dbg !16
  %subkernel.stack.1 = call i8* @llvm.stacksave(), !dbg !16
  %.46 = alloca { i8*, i32 }, align 8, !dbg !16
  %.46.repack = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.46, i32 0, i32 0, !dbg !16
  store i8* getelementptr inbounds ([2 x i8], [2 x i8]* @S.i, i32 0, i32 0), i8** %.46.repack, align 8, !dbg !16
  %.46.repack4 = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.46, i32 0, i32 1, !dbg !16
  store i32 2, i32* %.46.repack4, align 4, !dbg !16
  %subkernel.args.1 = alloca i8*, align 4, !dbg !16
  %subkernel.arg0.1 = alloca i32, align 4, !dbg !16
  store i32 10, i32* %subkernel.arg0.1, align 4, !dbg !16
  %3 = bitcast i8** %subkernel.args.1 to i32**, !dbg !16
  store i32* %subkernel.arg0.1, i32** %3, align 4, !dbg !16
  call void @subkernel_send_message(i32 3, i8 1, { i8*, i32 }* nonnull %.46, i8** nonnull %subkernel.args.1), !dbg !16
  call void @llvm.stackrestore(i8* %subkernel.stack.1), !dbg !16
  %subkernel.await.message.1 = call i8 @subkernel_await_message(i32 3, i64 10000, i8 1, i8 1), !dbg !17
  %subkernel.arg.stack.1 = call i8* @llvm.stacksave(), !dbg !17
  %rpc.ret.alloc.subkernel.ret.1 = alloca i32, align 4, !dbg !17
  %rpc.ret.ptr.subkernel.ret.1 = bitcast i32* %rpc.ret.alloc.subkernel.ret.1 to i8*, !dbg !17
  br label %rpc.head.subkernel.ret.1, !dbg !17

rpc.head.subkernel.ret.1:                         ; preds = %rpc.continue.subkernel.ret.1, %rpc.tail
  %rpc.ptr.subkernel.ret.1 = phi i8* [ %rpc.ret.ptr.subkernel.ret.1, %rpc.tail ], [ %rpc.alloc.subkernel.ret.1, %rpc.continue.subkernel.ret.1 ], !dbg !17
  %rpc.size.next.subkernel.ret.1 = call i32 @rpc_recv(i8* %rpc.ptr.subkernel.ret.1), !dbg !17
  %rpc.done.subkernel.ret.1 = icmp eq i32 %rpc.size.next.subkernel.ret.1, 0, !dbg !17
  br i1 %rpc.done.subkernel.ret.1, label %rpc.tail.subkernel.ret.1, label %rpc.continue.subkernel.ret.1, !dbg !17

rpc.continue.subkernel.ret.1:                     ; preds = %rpc.head.subkernel.ret.1
  %rpc.alloc.subkernel.ret.1 = alloca i8, i32 %rpc.size.next.subkernel.ret.1, align 8, !dbg !17
  br label %rpc.head.subkernel.ret.1, !dbg !17

rpc.tail.subkernel.ret.1:                         ; preds = %rpc.head.subkernel.ret.1
  %rpc.ret.subkernel.ret.1 = load i32, i32* %rpc.ret.alloc.subkernel.ret.1, align 4, !dbg !17
  call void @llvm.stackrestore(i8* %subkernel.arg.stack.1), !dbg !17
  call void @subkernel_await_finish(i32 3, i64 10000), !dbg !17
  %rpc.stack.1 = call i8* @llvm.stacksave(), !dbg !18
  %.61 = alloca { i8*, i32 }, align 8, !dbg !18
  %.61.repack = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.61, i32 0, i32 0, !dbg !18
  store i8* getelementptr inbounds ([3 x i8], [3 x i8]* @S.in.1, i32 0, i32 0), i8** %.61.repack, align 8, !dbg !18
  %.61.repack5 = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.61, i32 0, i32 1, !dbg !18
  store i32 3, i32* %.61.repack5, align 4, !dbg !18
  %rpc.args.1 = alloca i8*, align 4, !dbg !18
  %rpc.arg0.1 = alloca i32, align 4, !dbg !18
  store i32 %rpc.ret.subkernel.ret.1, i32* %rpc.arg0.1, align 4, !dbg !18
  %4 = bitcast i8** %rpc.args.1 to i32**, !dbg !18
  store i32* %rpc.arg0.1, i32** %4, align 4, !dbg !18
  call void @rpc_send(i32 2, { i8*, i32 }* nonnull %.61, i8** nonnull %rpc.args.1), !dbg !18
  call void @llvm.stackrestore(i8* %rpc.stack.1), !dbg !18
  br label %rpc.head.1, !dbg !18

rpc.head.1:                                       ; preds = %rpc.continue.1, %rpc.tail.subkernel.ret.1
  %rpc.ptr.1 = phi i8* [ %rpc.ret.ptr, %rpc.tail.subkernel.ret.1 ], [ %rpc.alloc.1, %rpc.continue.1 ], !dbg !18
  %rpc.size.next.1 = call i32 @rpc_recv(i8* %rpc.ptr.1), !dbg !18
  %rpc.done.1 = icmp eq i32 %rpc.size.next.1, 0, !dbg !18
  br i1 %rpc.done.1, label %rpc.tail.1, label %rpc.continue.1, !dbg !18

rpc.continue.1:                                   ; preds = %rpc.head.1
  %rpc.alloc.1 = alloca i8, i32 %rpc.size.next.1, align 8, !dbg !18
  br label %rpc.head.1, !dbg !18

rpc.tail.1:                                       ; preds = %rpc.head.1
  ret void, !dbg !18
}

; Function Attrs: mustprogress nofree nosync nounwind willreturn
declare i8* @llvm.stacksave() #1

; Function Attrs: nounwind
declare void @rpc_send_async(i32, { i8*, i32 }*, i8**) local_unnamed_addr #2

; Function Attrs: mustprogress nofree nosync nounwind willreturn
=======
define private fastcc void @_Z38artiq_run_test_subkernel.DMAPulses.runzz() unnamed_addr #0 personality i32 (...)* @__artiq_personality !dbg !11 {
entry:
<<<<<<< HEAD
  %rpc.ret.alloc.1 = alloca {}, align 8, !dbg !13
  call void @subkernel_load_run(i32 3, i1 false), !dbg !14
  call void @rtio_init(), !dbg !15
  %UNN.6.i = call i64 @rtio_get_counter(), !dbg !19
  %UNN.7.i = add i64 %UNN.6.i, 125000, !dbg !19
  %.10.i = lshr i64 %UNN.7.i, 32, !dbg !20
  %.11.i = trunc i64 %.10.i to i32, !dbg !20
  %.12.i = trunc i64 %UNN.7.i to i32, !dbg !20
  store atomic i32 %.11.i, i32* bitcast (i64* @now to i32*) seq_cst, align 8, !dbg !20
  store atomic i32 %.12.i, i32* bitcast (i64* getelementptr inbounds (i64, i64* @now, i32 1) to i32*) seq_cst, align 8, !dbg !20
  %UNN.4.i = call i64 @rtio_get_counter() #1, !dbg !21
  %UNN.5.i = add i64 %UNN.4.i, 125000, !dbg !21
  %now.hi.i = load i32, i32* bitcast (i64* @now to i32*), align 8, !dbg !24
  %.14.i = zext i32 %now.hi.i to i64, !dbg !24
  %.15.i = shl nuw i64 %.14.i, 32, !dbg !24
  %.16.i = and i64 %UNN.7.i, 4294967295, !dbg !24
  %.17.i = or i64 %.15.i, %.16.i, !dbg !24
  %UNN.7.i5 = icmp slt i64 %.17.i, %UNN.5.i, !dbg !24
  br i1 %UNN.7.i5, label %if.body.i, label %_Z41artiq.coredevice.core.Core.break_realtimeI26artiq.coredevice.core.CoreEzz.exit, !dbg !25

if.body.i:                                        ; preds = %entry
  %.20.i = lshr i64 %UNN.5.i, 32, !dbg !26
  %.21.i = trunc i64 %.20.i to i32, !dbg !26
  %.22.i = trunc i64 %UNN.5.i to i32, !dbg !26
  store atomic i32 %.21.i, i32* bitcast (i64* @now to i32*) seq_cst, align 8, !dbg !26
  store atomic i32 %.22.i, i32* bitcast (i64* getelementptr inbounds (i64, i64* @now, i32 1) to i32*) seq_cst, align 8, !dbg !26
  br label %_Z41artiq.coredevice.core.Core.break_realtimeI26artiq.coredevice.core.CoreEzz.exit, !dbg !26

_Z41artiq.coredevice.core.Core.break_realtimeI26artiq.coredevice.core.CoreEzz.exit: ; preds = %entry, %if.body.i
  call void @subkernel_load_run(i32 3, i1 true), !dbg !27
  %subkernel.stack = call i8* @llvm.stacksave(), !dbg !27
  %.28 = alloca { i8*, i32 }, align 8, !dbg !27
  %.28.repack = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.28, i32 0, i32 0, !dbg !27
  store i8* getelementptr inbounds ([3 x i8], [3 x i8]* @S.iI, i32 0, i32 0), i8** %.28.repack, align 8, !dbg !27
  %.28.repack1 = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.28, i32 0, i32 1, !dbg !27
  store i32 3, i32* %.28.repack1, align 4, !dbg !27
  %subkernel.args2 = alloca [2 x i8*], align 4, !dbg !27
  %subkernel.arg0 = alloca i32, align 4, !dbg !27
  %subkernel.args2.sub = getelementptr inbounds [2 x i8*], [2 x i8*]* %subkernel.args2, i32 0, i32 0
  store i32 57005, i32* %subkernel.arg0, align 4, !dbg !27
  %0 = bitcast [2 x i8*]* %subkernel.args2 to i32**, !dbg !27
  store i32* %subkernel.arg0, i32** %0, align 4, !dbg !27
  %subkernel.arg1 = alloca i64, align 8, !dbg !27
  store i64 3203334144, i64* %subkernel.arg1, align 8, !dbg !27
  %.36 = getelementptr inbounds [2 x i8*], [2 x i8*]* %subkernel.args2, i32 0, i32 1, !dbg !27
  %1 = bitcast i8** %.36 to i64**, !dbg !27
  store i64* %subkernel.arg1, i64** %1, align 4, !dbg !27
  call void @subkernel_send_message(i32 3, { i8*, i32 }* nonnull %.28, i8** nonnull %subkernel.args2.sub), !dbg !27
  call void @llvm.stackrestore(i8* %subkernel.stack), !dbg !27
  call void @subkernel_await_finish(i1 false, i32 3, i64 10000), !dbg !28
  call void @subkernel_await_message(i32 3, i64 10000), !dbg !28
  %subkernel.arg.stack = call i8* @llvm.stacksave(), !dbg !28
  %rpc.ret.alloc = alloca i32, align 4, !dbg !28
  %rpc.ret.ptr = bitcast i32* %rpc.ret.alloc to i8*, !dbg !28
  br label %rpc.head, !dbg !28

rpc.head:                                         ; preds = %rpc.continue, %_Z41artiq.coredevice.core.Core.break_realtimeI26artiq.coredevice.core.CoreEzz.exit
  %rpc.ptr = phi i8* [ %rpc.ret.ptr, %_Z41artiq.coredevice.core.Core.break_realtimeI26artiq.coredevice.core.CoreEzz.exit ], [ %rpc.alloc, %rpc.continue ], !dbg !28
  %rpc.size.next = call i32 @rpc_recv(i8* %rpc.ptr), !dbg !28
  %rpc.done = icmp eq i32 %rpc.size.next, 0, !dbg !28
  br i1 %rpc.done, label %rpc.tail, label %rpc.continue, !dbg !28

rpc.continue:                                     ; preds = %rpc.head
  %rpc.alloc = alloca i8, i32 %rpc.size.next, align 8, !dbg !28
  br label %rpc.head, !dbg !28

rpc.tail:                                         ; preds = %rpc.head
  %rpc.ret = load i32, i32* %rpc.ret.alloc, align 4, !dbg !28
  call void @llvm.stackrestore(i8* %subkernel.arg.stack), !dbg !28
  %rpc.stack = call i8* @llvm.stacksave(), !dbg !13
  %.47 = alloca { i8*, i32 }, align 8, !dbg !13
  %.47.repack = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.47, i32 0, i32 0, !dbg !13
  store i8* getelementptr inbounds ([3 x i8], [3 x i8]* @S.in.1, i32 0, i32 0), i8** %.47.repack, align 8, !dbg !13
  %.47.repack3 = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.47, i32 0, i32 1, !dbg !13
  store i32 3, i32* %.47.repack3, align 4, !dbg !13
  %rpc.args = alloca i8*, align 4, !dbg !13
  %rpc.arg0 = alloca i32, align 4, !dbg !13
  store i32 %rpc.ret, i32* %rpc.arg0, align 4, !dbg !13
  %2 = bitcast i8** %rpc.args to i32**, !dbg !13
  store i32* %rpc.arg0, i32** %2, align 4, !dbg !13
  call void @rpc_send(i32 2, { i8*, i32 }* nonnull %.47, i8** nonnull %rpc.args), !dbg !13
  call void @llvm.stackrestore(i8* %rpc.stack), !dbg !13
  %rpc.ret.ptr.1 = bitcast {}* %rpc.ret.alloc.1 to i8*, !dbg !13
  br label %rpc.head.1, !dbg !13

rpc.head.1:                                       ; preds = %rpc.continue.1, %rpc.tail
  %rpc.ptr.1 = phi i8* [ %rpc.ret.ptr.1, %rpc.tail ], [ %rpc.alloc.1, %rpc.continue.1 ], !dbg !13
  %rpc.size.next.1 = call i32 @rpc_recv(i8* %rpc.ptr.1), !dbg !13
  %rpc.done.1 = icmp eq i32 %rpc.size.next.1, 0, !dbg !13
  br i1 %rpc.done.1, label %rpc.tail.1, label %rpc.continue.1, !dbg !13

rpc.continue.1:                                   ; preds = %rpc.head.1
  %rpc.alloc.1 = alloca i8, i32 %rpc.size.next.1, align 8, !dbg !13
  br label %rpc.head.1, !dbg !13

rpc.tail.1:                                       ; preds = %rpc.head.1
  call void @llvm.stackrestore(i8* %rpc.stack), !dbg !13
  call void @subkernel_load_run(i32 4, i1 true), !dbg !29
  call void @subkernel_await_finish(i1 false, i32 4, i64 1000), !dbg !30
  call void @subkernel_await_message(i32 4, i64 1000), !dbg !30
  %subkernel.arg.stack.1 = call i8* @llvm.stacksave(), !dbg !30
  %rpc.ret.alloc.2 = alloca i32, align 4, !dbg !30
  %rpc.ret.ptr.2 = bitcast i32* %rpc.ret.alloc.2 to i8*, !dbg !30
  br label %rpc.head.2, !dbg !30

rpc.head.2:                                       ; preds = %rpc.continue.2, %rpc.tail.1
  %rpc.ptr.2 = phi i8* [ %rpc.ret.ptr.2, %rpc.tail.1 ], [ %rpc.alloc.2, %rpc.continue.2 ], !dbg !30
  %rpc.size.next.2 = call i32 @rpc_recv(i8* %rpc.ptr.2), !dbg !30
  %rpc.done.2 = icmp eq i32 %rpc.size.next.2, 0, !dbg !30
  br i1 %rpc.done.2, label %rpc.tail.2, label %rpc.continue.2, !dbg !30

rpc.continue.2:                                   ; preds = %rpc.head.2
  %rpc.alloc.2 = alloca i8, i32 %rpc.size.next.2, align 8, !dbg !30
  br label %rpc.head.2, !dbg !30

rpc.tail.2:                                       ; preds = %rpc.head.2
  %rpc.ret.2 = load i32, i32* %rpc.ret.alloc.2, align 4, !dbg !30
  call void @llvm.stackrestore(i8* %subkernel.arg.stack.1), !dbg !30
  %rpc.stack.1 = call i8* @llvm.stacksave(), !dbg !31
  %.71 = alloca { i8*, i32 }, align 8, !dbg !31
  %.71.repack = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.71, i32 0, i32 0, !dbg !31
  store i8* getelementptr inbounds ([3 x i8], [3 x i8]* @S.in.1, i32 0, i32 0), i8** %.71.repack, align 8, !dbg !31
  %.71.repack4 = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.71, i32 0, i32 1, !dbg !31
  store i32 3, i32* %.71.repack4, align 4, !dbg !31
  %rpc.args.1 = alloca i8*, align 4, !dbg !31
  %rpc.arg0.1 = alloca i32, align 4, !dbg !31
  store i32 %rpc.ret.2, i32* %rpc.arg0.1, align 4, !dbg !31
  %3 = bitcast i8** %rpc.args.1 to i32**, !dbg !31
  store i32* %rpc.arg0.1, i32** %3, align 4, !dbg !31
  call void @rpc_send(i32 2, { i8*, i32 }* nonnull %.71, i8** nonnull %rpc.args.1), !dbg !31
  call void @llvm.stackrestore(i8* %rpc.stack.1), !dbg !31
  br label %rpc.head.3, !dbg !31

rpc.head.3:                                       ; preds = %rpc.continue.3, %rpc.tail.2
  %rpc.ptr.3 = phi i8* [ %rpc.ret.ptr.1, %rpc.tail.2 ], [ %rpc.alloc.3, %rpc.continue.3 ], !dbg !31
  %rpc.size.next.3 = call i32 @rpc_recv(i8* %rpc.ptr.3), !dbg !31
  %rpc.done.3 = icmp eq i32 %rpc.size.next.3, 0, !dbg !31
  br i1 %rpc.done.3, label %rpc.tail.3, label %rpc.continue.3, !dbg !31

rpc.continue.3:                                   ; preds = %rpc.head.3
  %rpc.alloc.3 = alloca i8, i32 %rpc.size.next.3, align 8, !dbg !31
  br label %rpc.head.3, !dbg !31

rpc.tail.3:                                       ; preds = %rpc.head.3
  call void @llvm.stackrestore(i8* %rpc.stack.1), !dbg !31
  call void @subkernel_load_run(i32 5, i1 true), !dbg !32
  %now.hi = load i32, i32* bitcast (i64* @now to i32*), align 8, !dbg !33
  %now.lo = load i32, i32* bitcast (i64* getelementptr inbounds (i64, i64* @now, i32 1) to i32*), align 8, !dbg !33
  %.92 = zext i32 %now.hi to i64, !dbg !33
  %.93 = shl nuw i64 %.92, 32, !dbg !33
  %.94 = zext i32 %now.lo to i64, !dbg !33
  %.95 = or i64 %.93, %.94, !dbg !33
  %now.new = add i64 %.95, 1000000000, !dbg !33
  %.96 = lshr i64 %now.new, 32, !dbg !33
  %.97 = trunc i64 %.96 to i32, !dbg !33
  %.98 = trunc i64 %now.new to i32, !dbg !33
  store atomic i32 %.97, i32* bitcast (i64* @now to i32*) seq_cst, align 8, !dbg !33
  store atomic i32 %.98, i32* bitcast (i64* getelementptr inbounds (i64, i64* @now, i32 1) to i32*) seq_cst, align 8, !dbg !33
  call void @rtio_output(i32 2304, i32 1), !dbg !34
  %now.hi.i6 = load i32, i32* bitcast (i64* @now to i32*), align 8, !dbg !42
  %.25.i = zext i32 %now.hi.i6 to i64, !dbg !42
  %.26.i = shl nuw i64 %.25.i, 32, !dbg !42
  %.27.i = and i64 %now.new, 4294967295, !dbg !42
  %.28.i = or i64 %.26.i, %.27.i, !dbg !42
  %now.new.i = add i64 %.28.i, 1000000000, !dbg !42
  %.29.i = lshr i64 %now.new.i, 32, !dbg !42
  %.30.i = trunc i64 %.29.i to i32, !dbg !42
  %.31.i = trunc i64 %now.new.i to i32, !dbg !42
  store atomic i32 %.30.i, i32* bitcast (i64* @now to i32*) seq_cst, align 8, !dbg !42
  store atomic i32 %.31.i, i32* bitcast (i64* getelementptr inbounds (i64, i64* @now, i32 1) to i32*) seq_cst, align 8, !dbg !42
  call void @rtio_output(i32 2304, i32 0), !dbg !43
  %now.hi.1 = load i32, i32* bitcast (i64* @now to i32*), align 8, !dbg !47
  %.116 = zext i32 %now.hi.1 to i64, !dbg !47
  %.117 = shl nuw i64 %.116, 32, !dbg !47
  %.118 = and i64 %now.new.i, 4294967295, !dbg !47
  %.119 = or i64 %.117, %.118, !dbg !47
  %now.new.1 = add i64 %.119, 1000000000, !dbg !47
  %.120 = lshr i64 %now.new.1, 32, !dbg !47
  %.121 = trunc i64 %.120 to i32, !dbg !47
  %.122 = trunc i64 %now.new.1 to i32, !dbg !47
  store atomic i32 %.121, i32* bitcast (i64* @now to i32*) seq_cst, align 8, !dbg !47
  store atomic i32 %.122, i32* bitcast (i64* getelementptr inbounds (i64, i64* @now, i32 1) to i32*) seq_cst, align 8, !dbg !47
  ret void, !dbg !47
=======
  %subkernel.args2 = alloca [0 x i8*], align 4, !dbg !13
  call void @rtio_init(), !dbg !14
  %UNN.6.i = call i64 @rtio_get_counter(), !dbg !18
  %UNN.7.i = add i64 %UNN.6.i, 125000, !dbg !18
  %.10.i = lshr i64 %UNN.7.i, 32, !dbg !19
  %.11.i = trunc i64 %.10.i to i32, !dbg !19
  %.12.i = trunc i64 %UNN.7.i to i32, !dbg !19
  store atomic i32 %.11.i, i32* bitcast (i64* @now to i32*) seq_cst, align 8, !dbg !19
  store atomic i32 %.12.i, i32* bitcast (i64* getelementptr inbounds (i64, i64* @now, i32 1) to i32*) seq_cst, align 8, !dbg !19
  %UNN.4.i = call i64 @rtio_get_counter() #1, !dbg !20
  %UNN.5.i = add i64 %UNN.4.i, 125000, !dbg !20
  %now.hi.i = load i32, i32* bitcast (i64* @now to i32*), align 8, !dbg !23
  %.14.i = zext i32 %now.hi.i to i64, !dbg !23
  %.15.i = shl nuw i64 %.14.i, 32, !dbg !23
  %.16.i = and i64 %UNN.7.i, 4294967295, !dbg !23
  %.17.i = or i64 %.15.i, %.16.i, !dbg !23
  %UNN.7.i3 = icmp slt i64 %.17.i, %UNN.5.i, !dbg !23
  br i1 %UNN.7.i3, label %if.body.i, label %_Z41artiq.coredevice.core.Core.break_realtimeI26artiq.coredevice.core.CoreEzz.exit, !dbg !24

if.body.i:                                        ; preds = %entry
  %.20.i = lshr i64 %UNN.5.i, 32, !dbg !25
  %.21.i = trunc i64 %.20.i to i32, !dbg !25
  %.22.i = trunc i64 %UNN.5.i to i32, !dbg !25
  store atomic i32 %.21.i, i32* bitcast (i64* @now to i32*) seq_cst, align 8, !dbg !25
  store atomic i32 %.22.i, i32* bitcast (i64* getelementptr inbounds (i64, i64* @now, i32 1) to i32*) seq_cst, align 8, !dbg !25
  br label %_Z41artiq.coredevice.core.Core.break_realtimeI26artiq.coredevice.core.CoreEzz.exit, !dbg !25

_Z41artiq.coredevice.core.Core.break_realtimeI26artiq.coredevice.core.CoreEzz.exit: ; preds = %entry, %if.body.i
  call void @subkernel_load_run(i32 2, i1 true), !dbg !13
  %subkernel.stack = call i8* @llvm.stacksave(), !dbg !13
  %.28 = alloca { i8*, i32 }, align 8, !dbg !13
  %.28.repack = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.28, i32 0, i32 0, !dbg !13
  store i8* getelementptr inbounds ([1 x i8], [1 x i8]* @S., i32 0, i32 0), i8** %.28.repack, align 8, !dbg !13
  %.28.repack1 = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.28, i32 0, i32 1, !dbg !13
  store i32 1, i32* %.28.repack1, align 4, !dbg !13
  %subkernel.args2.sub = getelementptr inbounds [0 x i8*], [0 x i8*]* %subkernel.args2, i32 0, i32 0
  call void @subkernel_send_message(i32 2, { i8*, i32 }* nonnull %.28, i8** nonnull %subkernel.args2.sub), !dbg !13
  call void @llvm.stackrestore(i8* %subkernel.stack), !dbg !13
  call void @subkernel_await_finish(i1 false, i32 2, i64 10000), !dbg !26
  br label %while.head, !dbg !27

while.head:                                       ; preds = %while.head, %_Z41artiq.coredevice.core.Core.break_realtimeI26artiq.coredevice.core.CoreEzz.exit
  call void @rtio_output(i32 2304, i32 1), !dbg !28
  %now.hi.i4 = load i32, i32* bitcast (i64* @now to i32*), align 8, !dbg !36
  %now.lo.i5 = load i32, i32* bitcast (i64* getelementptr inbounds (i64, i64* @now, i32 1) to i32*), align 8, !dbg !36
  %.25.i = zext i32 %now.hi.i4 to i64, !dbg !36
  %.26.i = shl nuw i64 %.25.i, 32, !dbg !36
  %.27.i = zext i32 %now.lo.i5 to i64, !dbg !36
  %.28.i = or i64 %.26.i, %.27.i, !dbg !36
  %now.new.i = add i64 %.28.i, 1000000000, !dbg !36
  %.29.i = lshr i64 %now.new.i, 32, !dbg !36
  %.30.i = trunc i64 %.29.i to i32, !dbg !36
  %.31.i = trunc i64 %now.new.i to i32, !dbg !36
  store atomic i32 %.30.i, i32* bitcast (i64* @now to i32*) seq_cst, align 8, !dbg !36
  store atomic i32 %.31.i, i32* bitcast (i64* getelementptr inbounds (i64, i64* @now, i32 1) to i32*) seq_cst, align 8, !dbg !36
  call void @rtio_output(i32 2304, i32 0), !dbg !37
  %now.hi = load i32, i32* bitcast (i64* @now to i32*), align 8, !dbg !41
  %.49 = zext i32 %now.hi to i64, !dbg !41
  %.50 = shl nuw i64 %.49, 32, !dbg !41
  %.51 = and i64 %now.new.i, 4294967295, !dbg !41
  %.52 = or i64 %.50, %.51, !dbg !41
  %now.new = add i64 %.52, 1000000000, !dbg !41
  %.53 = lshr i64 %now.new, 32, !dbg !41
  %.54 = trunc i64 %.53 to i32, !dbg !41
  %.55 = trunc i64 %now.new to i32, !dbg !41
  store atomic i32 %.54, i32* bitcast (i64* @now to i32*) seq_cst, align 8, !dbg !41
  store atomic i32 %.55, i32* bitcast (i64* getelementptr inbounds (i64, i64* @now, i32 1) to i32*) seq_cst, align 8, !dbg !41
  br label %while.head, !dbg !41
>>>>>>> 76594e85a (don't waste time and bandwidth with returning Nones)
}

; Function Attrs: nounwind
declare i8* @llvm.stacksave() #1

; Function Attrs: nounwind
declare void @rpc_send_async(i32, { i8*, i32 }*, i8**) local_unnamed_addr #1

; Function Attrs: nounwind
>>>>>>> ff18ac7b5 (don't waste time and bandwidth with returning Nones)
declare void @llvm.stackrestore(i8*) #1

declare void @subkernel_load_run(i32, i1) local_unnamed_addr

<<<<<<< HEAD
declare void @subkernel_send_message(i32, i8, { i8*, i32 }*, i8**) local_unnamed_addr

declare i8 @subkernel_await_message(i32, i64, i8, i8) local_unnamed_addr

declare i32 @rpc_recv(i8*) local_unnamed_addr

declare void @subkernel_await_finish(i32, i64) local_unnamed_addr

; Function Attrs: nounwind
declare void @rpc_send(i32, { i8*, i32 }*, i8**) local_unnamed_addr #2

attributes #0 = { uwtable }
attributes #1 = { mustprogress nofree nosync nounwind willreturn }
attributes #2 = { nounwind }
=======
declare void @subkernel_send_message(i32, { i8*, i32 }*, i8**) local_unnamed_addr

declare void @subkernel_await_finish(i1, i32, i64) local_unnamed_addr

<<<<<<< HEAD
declare void @subkernel_await_message(i32, i64) local_unnamed_addr

declare i32 @rpc_recv(i8*) local_unnamed_addr

; Function Attrs: nounwind
declare void @rpc_send(i32, { i8*, i32 }*, i8**) local_unnamed_addr #1

=======
>>>>>>> 76594e85a (don't waste time and bandwidth with returning Nones)
declare void @rtio_init() local_unnamed_addr

; Function Attrs: inaccessiblememonly nounwind
declare i64 @rtio_get_counter() local_unnamed_addr #2

; Function Attrs: inaccessiblememonly
declare void @rtio_output(i32, i32) local_unnamed_addr #3

attributes #0 = { uwtable }
attributes #1 = { nounwind }
attributes #2 = { inaccessiblememonly nounwind }
attributes #3 = { inaccessiblememonly }
>>>>>>> ff18ac7b5 (don't waste time and bandwidth with returning Nones)

!llvm.ident = !{!0}
!llvm.module.flags = !{!1, !2}
!llvm.dbg.cu = !{!3}

!0 = !{!"ARTIQ"}
!1 = !{i32 2, !"Debug Info Version", i32 3}
!2 = !{i32 2, !"Dwarf Version", i32 4}
!3 = distinct !DICompileUnit(language: DW_LANG_Python, file: !4, producer: "ARTIQ", isOptimized: false, runtimeVersion: 0, emissionKind: LineTablesOnly)
!4 = !DIFile(filename: "<synthesized>", directory: "")
!5 = distinct !DISubprogram(name: "__modinit__", linkageName: "__modinit__", scope: !4, file: !4, line: 1, type: !6, scopeLine: 1, spFlags: DISPFlagDefinition, unit: !3, retainedNodes: !8)
!6 = !DISubroutineType(types: !7)
!7 = !{null}
!8 = !{}
!9 = !DILocation(line: 1, scope: !5)
!10 = !DILocation(line: 1, column: 60, scope: !5)
<<<<<<< HEAD
!11 = distinct !DISubprogram(name: "_Z42artiq_run_test_subkernel_opt.DMAPulses.runzz", linkageName: "_Z42artiq_run_test_subkernel_opt.DMAPulses.runzz", scope: !12, file: !12, line: 21, type: !6, scopeLine: 21, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!12 = !DIFile(filename: "test_subkernel_opt.py", directory: "")
!13 = !DILocation(line: 24, column: 8, scope: !11)
!14 = !DILocation(line: 22, column: 8, scope: !11)
!15 = !DILocation(line: 23, column: 14, scope: !11)
!16 = !DILocation(line: 31, column: 8, scope: !11)
!17 = !DILocation(line: 32, column: 14, scope: !11)
!18 = !DILocation(line: 33, column: 8, scope: !11)
=======
<<<<<<< HEAD
!11 = distinct !DISubprogram(name: "_Z38artiq_run_test_subkernel.DMAPulses.runzz", linkageName: "_Z38artiq_run_test_subkernel.DMAPulses.runzz", scope: !12, file: !12, line: 35, type: !6, scopeLine: 35, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!12 = !DIFile(filename: "test_subkernel.py", directory: "")
!13 = !DILocation(line: 41, column: 8, scope: !11)
!14 = !DILocation(line: 36, column: 8, scope: !11)
!15 = !DILocation(line: 325, column: 8, scope: !16, inlinedAt: !18)
!16 = distinct !DISubprogram(name: "_Z32artiq.coredevice.core.Core.resetI26artiq.coredevice.core.CoreEzz", linkageName: "_Z32artiq.coredevice.core.Core.resetI26artiq.coredevice.core.CoreEzz", scope: !17, file: !17, line: 321, type: !6, scopeLine: 321, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!17 = !DIFile(filename: "core.py", directory: "/home/spaqin/m-labs/artiq/artiq/coredevice")
!18 = distinct !DILocation(line: 37, column: 8, scope: !11)
!19 = !DILocation(line: 326, column: 14, scope: !16, inlinedAt: !18)
!20 = !DILocation(line: 326, column: 8, scope: !16, inlinedAt: !18)
!21 = !DILocation(line: 335, column: 18, scope: !22, inlinedAt: !23)
!22 = distinct !DISubprogram(name: "_Z41artiq.coredevice.core.Core.break_realtimeI26artiq.coredevice.core.CoreEzz", linkageName: "_Z41artiq.coredevice.core.Core.break_realtimeI26artiq.coredevice.core.CoreEzz", scope: !17, file: !17, line: 329, type: !6, scopeLine: 329, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!23 = distinct !DILocation(line: 38, column: 8, scope: !11)
!24 = !DILocation(line: 336, column: 11, scope: !22, inlinedAt: !23)
!25 = !DILocation(line: 336, column: 8, scope: !22, inlinedAt: !23)
!26 = !DILocation(line: 337, column: 12, scope: !22, inlinedAt: !23)
!27 = !DILocation(line: 39, column: 8, scope: !11)
!28 = !DILocation(line: 40, column: 14, scope: !11)
!29 = !DILocation(line: 42, column: 8, scope: !11)
!30 = !DILocation(line: 43, column: 14, scope: !11)
!31 = !DILocation(line: 44, column: 8, scope: !11)
!32 = !DILocation(line: 45, column: 8, scope: !11)
!33 = !DILocation(line: 46, column: 8, scope: !11)
!34 = !DILocation(line: 49, column: 8, scope: !35, inlinedAt: !37)
!35 = distinct !DISubprogram(name: "_Z33artiq.coredevice.ttl.TTLOut.set_oI27artiq.coredevice.ttl.TTLOutEzz", linkageName: "_Z33artiq.coredevice.ttl.TTLOut.set_oI27artiq.coredevice.ttl.TTLOutEzz", scope: !36, file: !36, line: 48, type: !6, scopeLine: 48, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!36 = !DIFile(filename: "ttl.py", directory: "/home/spaqin/m-labs/artiq/artiq/coredevice")
!37 = distinct !DILocation(line: 57, column: 8, scope: !38, inlinedAt: !39)
!38 = distinct !DISubprogram(name: "_Z30artiq.coredevice.ttl.TTLOut.onI27artiq.coredevice.ttl.TTLOutEzz", linkageName: "_Z30artiq.coredevice.ttl.TTLOut.onI27artiq.coredevice.ttl.TTLOutEzz", scope: !36, file: !36, line: 52, type: !6, scopeLine: 52, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!39 = distinct !DILocation(line: 83, column: 8, scope: !40, inlinedAt: !41)
!40 = distinct !DISubprogram(name: "_Z33artiq.coredevice.ttl.TTLOut.pulseI27artiq.coredevice.ttl.TTLOutEzz", linkageName: "_Z33artiq.coredevice.ttl.TTLOut.pulseI27artiq.coredevice.ttl.TTLOutEzz", scope: !36, file: !36, line: 78, type: !6, scopeLine: 78, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!41 = distinct !DILocation(line: 47, column: 8, scope: !11)
!42 = !DILocation(line: 84, column: 8, scope: !40, inlinedAt: !41)
!43 = !DILocation(line: 49, column: 8, scope: !35, inlinedAt: !44)
!44 = distinct !DILocation(line: 65, column: 8, scope: !45, inlinedAt: !46)
!45 = distinct !DISubprogram(name: "_Z31artiq.coredevice.ttl.TTLOut.offI27artiq.coredevice.ttl.TTLOutEzz", linkageName: "_Z31artiq.coredevice.ttl.TTLOut.offI27artiq.coredevice.ttl.TTLOutEzz", scope: !36, file: !36, line: 60, type: !6, scopeLine: 60, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!46 = distinct !DILocation(line: 85, column: 8, scope: !40, inlinedAt: !41)
!47 = !DILocation(line: 48, column: 8, scope: !11)
=======
!11 = distinct !DISubprogram(name: "_Z38artiq_run_test_subkernel.DMAPulses.runzz", linkageName: "_Z38artiq_run_test_subkernel.DMAPulses.runzz", scope: !12, file: !12, line: 28, type: !6, scopeLine: 28, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!12 = !DIFile(filename: "test_subkernel.py", directory: "")
!13 = !DILocation(line: 33, column: 8, scope: !11)
!14 = !DILocation(line: 320, column: 8, scope: !15, inlinedAt: !17)
!15 = distinct !DISubprogram(name: "_Z32artiq.coredevice.core.Core.resetI26artiq.coredevice.core.CoreEzz", linkageName: "_Z32artiq.coredevice.core.Core.resetI26artiq.coredevice.core.CoreEzz", scope: !16, file: !16, line: 316, type: !6, scopeLine: 316, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!16 = !DIFile(filename: "core.py", directory: "/home/spaqin/m-labs/artiq/artiq/coredevice")
!17 = distinct !DILocation(line: 29, column: 8, scope: !11)
!18 = !DILocation(line: 321, column: 14, scope: !15, inlinedAt: !17)
!19 = !DILocation(line: 321, column: 8, scope: !15, inlinedAt: !17)
!20 = !DILocation(line: 330, column: 18, scope: !21, inlinedAt: !22)
!21 = distinct !DISubprogram(name: "_Z41artiq.coredevice.core.Core.break_realtimeI26artiq.coredevice.core.CoreEzz", linkageName: "_Z41artiq.coredevice.core.Core.break_realtimeI26artiq.coredevice.core.CoreEzz", scope: !16, file: !16, line: 324, type: !6, scopeLine: 324, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!22 = distinct !DILocation(line: 30, column: 8, scope: !11)
!23 = !DILocation(line: 331, column: 11, scope: !21, inlinedAt: !22)
!24 = !DILocation(line: 331, column: 8, scope: !21, inlinedAt: !22)
!25 = !DILocation(line: 332, column: 12, scope: !21, inlinedAt: !22)
!26 = !DILocation(line: 34, column: 8, scope: !11)
!27 = !DILocation(line: 35, column: 8, scope: !11)
!28 = !DILocation(line: 49, column: 8, scope: !29, inlinedAt: !31)
!29 = distinct !DISubprogram(name: "_Z33artiq.coredevice.ttl.TTLOut.set_oI27artiq.coredevice.ttl.TTLOutEzz", linkageName: "_Z33artiq.coredevice.ttl.TTLOut.set_oI27artiq.coredevice.ttl.TTLOutEzz", scope: !30, file: !30, line: 48, type: !6, scopeLine: 48, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!30 = !DIFile(filename: "ttl.py", directory: "/home/spaqin/m-labs/artiq/artiq/coredevice")
!31 = distinct !DILocation(line: 57, column: 8, scope: !32, inlinedAt: !33)
!32 = distinct !DISubprogram(name: "_Z30artiq.coredevice.ttl.TTLOut.onI27artiq.coredevice.ttl.TTLOutEzz", linkageName: "_Z30artiq.coredevice.ttl.TTLOut.onI27artiq.coredevice.ttl.TTLOutEzz", scope: !30, file: !30, line: 52, type: !6, scopeLine: 52, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!33 = distinct !DILocation(line: 83, column: 8, scope: !34, inlinedAt: !35)
!34 = distinct !DISubprogram(name: "_Z33artiq.coredevice.ttl.TTLOut.pulseI27artiq.coredevice.ttl.TTLOutEzz", linkageName: "_Z33artiq.coredevice.ttl.TTLOut.pulseI27artiq.coredevice.ttl.TTLOutEzz", scope: !30, file: !30, line: 78, type: !6, scopeLine: 78, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!35 = distinct !DILocation(line: 36, column: 12, scope: !11)
!36 = !DILocation(line: 84, column: 8, scope: !34, inlinedAt: !35)
!37 = !DILocation(line: 49, column: 8, scope: !29, inlinedAt: !38)
!38 = distinct !DILocation(line: 65, column: 8, scope: !39, inlinedAt: !40)
!39 = distinct !DISubprogram(name: "_Z31artiq.coredevice.ttl.TTLOut.offI27artiq.coredevice.ttl.TTLOutEzz", linkageName: "_Z31artiq.coredevice.ttl.TTLOut.offI27artiq.coredevice.ttl.TTLOutEzz", scope: !30, file: !30, line: 60, type: !6, scopeLine: 60, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!40 = distinct !DILocation(line: 85, column: 8, scope: !34, inlinedAt: !35)
!41 = !DILocation(line: 37, column: 12, scope: !11)
>>>>>>> 76594e85a (don't waste time and bandwidth with returning Nones)
>>>>>>> ff18ac7b5 (don't waste time and bandwidth with returning Nones)
