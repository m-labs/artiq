; ModuleID = '<string>'
source_filename = "<string>"
target datalayout = "e-m:e-p:32:32-i64:64-n32-S128"
target triple = "riscv32-unknown-linux"

%D.5 = type { %A.4**, i8** }
%A.4 = type { i32, { i8*, i32 }, { i8*, i32 } }

@S.nn = private unnamed_addr constant [3 x i8] c"n:n"
@S.ii = private unnamed_addr constant [3 x i8] c"ii:"
@S.i = private unnamed_addr constant [2 x i8] c"i:"
@S.in.1 = private unnamed_addr constant [3 x i8] c"i:n"
@typeinfo = local_unnamed_addr global [1 x %D.5*] zeroinitializer

; Function Attrs: uwtable
define void @__modinit__(i8* nocapture readnone %.1) local_unnamed_addr #0 personality i32 (...)* @__artiq_personality !dbg !5 {
entry:
  %rpc.arg0 = alloca {}, align 8, !dbg !9
  call fastcc void @_Z42artiq_run_test_subkernel_opt.DMAPulses.runzz(), !dbg !10
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
declare void @llvm.stackrestore(i8*) #1

declare void @subkernel_load_run(i32, i1) local_unnamed_addr

declare void @subkernel_send_message(i32, i8, { i8*, i32 }*, i8**) local_unnamed_addr

declare i8 @subkernel_await_message(i32, i64, i8, i8) local_unnamed_addr

declare i32 @rpc_recv(i8*) local_unnamed_addr

declare void @subkernel_await_finish(i32, i64) local_unnamed_addr

; Function Attrs: nounwind
declare void @rpc_send(i32, { i8*, i32 }*, i8**) local_unnamed_addr #2

attributes #0 = { uwtable }
attributes #1 = { mustprogress nofree nosync nounwind willreturn }
attributes #2 = { nounwind }

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
!11 = distinct !DISubprogram(name: "_Z42artiq_run_test_subkernel_opt.DMAPulses.runzz", linkageName: "_Z42artiq_run_test_subkernel_opt.DMAPulses.runzz", scope: !12, file: !12, line: 21, type: !6, scopeLine: 21, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!12 = !DIFile(filename: "test_subkernel_opt.py", directory: "")
!13 = !DILocation(line: 24, column: 8, scope: !11)
!14 = !DILocation(line: 22, column: 8, scope: !11)
!15 = !DILocation(line: 23, column: 14, scope: !11)
!16 = !DILocation(line: 31, column: 8, scope: !11)
!17 = !DILocation(line: 32, column: 14, scope: !11)
!18 = !DILocation(line: 33, column: 8, scope: !11)
