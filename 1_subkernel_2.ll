; ModuleID = '<string>'
source_filename = "<string>"
target datalayout = "e-m:e-p:32:32-i64:64-n32-S128"
target triple = "riscv32-unknown-linux"

<<<<<<< HEAD
@S.i = private unnamed_addr constant [2 x i8] c"i:"
=======
<<<<<<< HEAD
@S.i = private unnamed_addr constant [2 x i8] c"i:"
=======
@now = external local_unnamed_addr global i64
>>>>>>> 76594e85a (don't waste time and bandwidth with returning Nones)
>>>>>>> ff18ac7b5 (don't waste time and bandwidth with returning Nones)

; Function Attrs: uwtable
define void @__modinit__(i8* nocapture readnone %.1) local_unnamed_addr #0 personality i32 (...)* @__artiq_personality !dbg !5 {
entry:
<<<<<<< HEAD
  %.15.i = alloca { i8*, i32 }, align 8, !dbg !9
  %subkernel.return.i = alloca i8*, align 4, !dbg !9
  %subkernel.retval.i = alloca i32, align 4, !dbg !9
  %subkernel.await.args = call i8 @subkernel_await_message(i32 0, i64 10000, i8 2, i8 3), !dbg !13
  %subkernel.arg.stack = call i8* @llvm.stacksave(), !dbg !13
  %rpc.ret.alloc.a = alloca i32, align 4, !dbg !13
  %rpc.ret.ptr.a = bitcast i32* %rpc.ret.alloc.a to i8*, !dbg !13
  br label %rpc.head.a, !dbg !13

rpc.head.a:                                       ; preds = %rpc.continue.a, %entry
  %rpc.ptr.a = phi i8* [ %rpc.ret.ptr.a, %entry ], [ %rpc.alloc.a, %rpc.continue.a ], !dbg !13
  %rpc.size.next.a = call i32 @rpc_recv(i8* %rpc.ptr.a), !dbg !13
  %rpc.done.a = icmp eq i32 %rpc.size.next.a, 0, !dbg !13
  br i1 %rpc.done.a, label %rpc.tail.a, label %rpc.continue.a, !dbg !13

rpc.continue.a:                                   ; preds = %rpc.head.a
  %rpc.alloc.a = alloca i8, i32 %rpc.size.next.a, align 8, !dbg !13
  br label %rpc.head.a, !dbg !13

rpc.tail.a:                                       ; preds = %rpc.head.a
  %rpc.ret.a = load i32, i32* %rpc.ret.alloc.a, align 4, !dbg !13
  call void @llvm.stackrestore(i8* %subkernel.arg.stack), !dbg !13
  %subkernel.arg.stack.1 = call i8* @llvm.stacksave(), !dbg !13
  %rpc.ret.alloc.b = alloca i32, align 4, !dbg !13
  %rpc.ret.ptr.b = bitcast i32* %rpc.ret.alloc.b to i8*, !dbg !13
  br label %rpc.head.b, !dbg !13

rpc.head.b:                                       ; preds = %rpc.continue.b, %rpc.tail.a
  %rpc.ptr.b = phi i8* [ %rpc.ret.ptr.b, %rpc.tail.a ], [ %rpc.alloc.b, %rpc.continue.b ], !dbg !13
  %rpc.size.next.b = call i32 @rpc_recv(i8* %rpc.ptr.b), !dbg !13
  %rpc.done.b = icmp eq i32 %rpc.size.next.b, 0, !dbg !13
  br i1 %rpc.done.b, label %rpc.tail.b, label %rpc.continue.b, !dbg !13

rpc.continue.b:                                   ; preds = %rpc.head.b
  %rpc.alloc.b = alloca i8, i32 %rpc.size.next.b, align 8, !dbg !13
  br label %rpc.head.b, !dbg !13

rpc.tail.b:                                       ; preds = %rpc.head.b
  %rpc.ret.b = load i32, i32* %rpc.ret.alloc.b, align 4, !dbg !13
  call void @llvm.stackrestore(i8* %subkernel.arg.stack.1), !dbg !13
  %.16 = icmp ugt i8 %subkernel.await.args, 1, !dbg !13
  br i1 %.16, label %optarg.get.c, label %optarg.tail.c, !dbg !13

optarg.get.c:                                     ; preds = %rpc.tail.b
  %subkernel.arg.stack.2 = call i8* @llvm.stacksave(), !dbg !13
  %rpc.ret.alloc.c = alloca i32, align 4, !dbg !13
  %rpc.ret.ptr.c = bitcast i32* %rpc.ret.alloc.c to i8*, !dbg !13
  br label %rpc.head.c, !dbg !13

rpc.head.c:                                       ; preds = %rpc.continue.c, %optarg.get.c
  %rpc.ptr.c = phi i8* [ %rpc.ret.ptr.c, %optarg.get.c ], [ %rpc.alloc.c, %rpc.continue.c ], !dbg !13
  %rpc.size.next.c = call i32 @rpc_recv(i8* %rpc.ptr.c), !dbg !13
  %rpc.done.c = icmp eq i32 %rpc.size.next.c, 0, !dbg !13
  br i1 %rpc.done.c, label %rpc.tail.c, label %rpc.continue.c, !dbg !13

rpc.continue.c:                                   ; preds = %rpc.head.c
  %rpc.alloc.c = alloca i8, i32 %rpc.size.next.c, align 8, !dbg !13
  br label %rpc.head.c, !dbg !13

rpc.tail.c:                                       ; preds = %rpc.head.c
  %rpc.ret.c = load i32, i32* %rpc.ret.alloc.c, align 4, !dbg !13
  call void @llvm.stackrestore(i8* %subkernel.arg.stack.2), !dbg !13
  br label %optarg.tail.c, !dbg !13

optarg.tail.c:                                    ; preds = %rpc.tail.c, %rpc.tail.b
  %DEF.c.i = phi i32 [ %rpc.ret.c, %rpc.tail.c ], [ 3, %rpc.tail.b ], !dbg !13
  %0 = bitcast { i8*, i32 }* %.15.i to i8*, !dbg !14
  call void @llvm.lifetime.start.p0i8(i64 8, i8* nonnull %0), !dbg !14
  %1 = bitcast i8** %subkernel.return.i to i8*, !dbg !14
  call void @llvm.lifetime.start.p0i8(i64 4, i8* nonnull %1), !dbg !14
  %2 = bitcast i32* %subkernel.retval.i to i8*, !dbg !14
  call void @llvm.lifetime.start.p0i8(i64 4, i8* nonnull %2), !dbg !14
  %UNN.5.i = sub i32 %rpc.ret.a, %rpc.ret.b, !dbg !15
  %UNN.6.i = add i32 %UNN.5.i, %DEF.c.i, !dbg !15
  %.15.repack.i = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.15.i, i32 0, i32 0, !dbg !9
  store i8* getelementptr inbounds ([2 x i8], [2 x i8]* @S.i, i32 0, i32 0), i8** %.15.repack.i, align 8, !dbg !9
  %.15.repack1.i = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.15.i, i32 0, i32 1, !dbg !9
  store i32 2, i32* %.15.repack1.i, align 4, !dbg !9
  store i32 %UNN.6.i, i32* %subkernel.retval.i, align 4, !dbg !9
  %3 = bitcast i8** %subkernel.return.i to i32**, !dbg !9
  store i32* %subkernel.retval.i, i32** %3, align 4, !dbg !9
  call void @subkernel_send_message(i32 0, i8 1, { i8*, i32 }* nonnull %.15.i, i8** nonnull %subkernel.return.i), !dbg !9
=======
<<<<<<< HEAD
  %.12.i = alloca { i8*, i32 }, align 8, !dbg !9
  %subkernel.return.i = alloca i8*, align 4, !dbg !9
  %subkernel.retval.i = alloca i32, align 4, !dbg !9
  %0 = bitcast { i8*, i32 }* %.12.i to i8*, !dbg !9
  call void @llvm.lifetime.start.p0i8(i64 8, i8* nonnull %0), !dbg !9
  %1 = bitcast i8** %subkernel.return.i to i8*, !dbg !9
  call void @llvm.lifetime.start.p0i8(i64 4, i8* nonnull %1), !dbg !9
  %2 = bitcast i32* %subkernel.retval.i to i8*, !dbg !9
  call void @llvm.lifetime.start.p0i8(i64 4, i8* nonnull %2), !dbg !9
  %.12.repack.i = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.12.i, i32 0, i32 0, !dbg !9
  store i8* getelementptr inbounds ([2 x i8], [2 x i8]* @S.i, i32 0, i32 0), i8** %.12.repack.i, align 8, !dbg !9
  %.12.repack1.i = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.12.i, i32 0, i32 1, !dbg !9
  store i32 2, i32* %.12.repack1.i, align 4, !dbg !9
  store i32 -559037225, i32* %subkernel.retval.i, align 4, !dbg !9
  %3 = bitcast i8** %subkernel.return.i to i32**, !dbg !9
  store i32* %subkernel.retval.i, i32** %3, align 4, !dbg !9
  call void @subkernel_send_message(i32 0, { i8*, i32 }* nonnull %.12.i, i8** nonnull %subkernel.return.i), !dbg !9
>>>>>>> ff18ac7b5 (don't waste time and bandwidth with returning Nones)
  call void @llvm.lifetime.end.p0i8(i64 8, i8* nonnull %0), !dbg !9
  call void @llvm.lifetime.end.p0i8(i64 4, i8* nonnull %1), !dbg !9
  call void @llvm.lifetime.end.p0i8(i64 4, i8* nonnull %2), !dbg !9
  ret void, !dbg !13
<<<<<<< HEAD
=======
=======
  call void @rtio_output(i32 16779264, i32 1), !dbg !9
  %now.hi.i.i = load i32, i32* bitcast (i64* @now to i32*), align 8, !dbg !20
  %now.lo.i.i = load i32, i32* bitcast (i64* getelementptr inbounds (i64, i64* @now, i32 1) to i32*), align 8, !dbg !20
  %.25.i.i = zext i32 %now.hi.i.i to i64, !dbg !20
  %.26.i.i = shl nuw i64 %.25.i.i, 32, !dbg !20
  %.27.i.i = zext i32 %now.lo.i.i to i64, !dbg !20
  %.28.i.i = or i64 %.26.i.i, %.27.i.i, !dbg !20
  %now.new.i.i = add i64 %.28.i.i, 1000000000, !dbg !20
  %.29.i.i = lshr i64 %now.new.i.i, 32, !dbg !20
  %.30.i.i = trunc i64 %.29.i.i to i32, !dbg !20
  %.31.i.i = trunc i64 %now.new.i.i to i32, !dbg !20
  store atomic i32 %.30.i.i, i32* bitcast (i64* @now to i32*) seq_cst, align 8, !dbg !20
  store atomic i32 %.31.i.i, i32* bitcast (i64* getelementptr inbounds (i64, i64* @now, i32 1) to i32*) seq_cst, align 8, !dbg !20
  call void @rtio_output(i32 16779264, i32 0), !dbg !21
  ret void, !dbg !25
>>>>>>> 76594e85a (don't waste time and bandwidth with returning Nones)
>>>>>>> ff18ac7b5 (don't waste time and bandwidth with returning Nones)
}

declare i32 @__artiq_personality(...)

<<<<<<< HEAD
declare i8 @subkernel_await_message(i32, i64, i8, i8) local_unnamed_addr

; Function Attrs: mustprogress nofree nosync nounwind willreturn
declare i8* @llvm.stacksave() #1

declare i32 @rpc_recv(i8*) local_unnamed_addr

; Function Attrs: mustprogress nofree nosync nounwind willreturn
declare void @llvm.stackrestore(i8*) #1

declare void @subkernel_send_message(i32, i8, { i8*, i32 }*, i8**) local_unnamed_addr

; Function Attrs: argmemonly nofree nosync nounwind willreturn
declare void @llvm.lifetime.start.p0i8(i64 immarg, i8* nocapture) #2

; Function Attrs: argmemonly nofree nosync nounwind willreturn
declare void @llvm.lifetime.end.p0i8(i64 immarg, i8* nocapture) #2

attributes #0 = { uwtable }
attributes #1 = { mustprogress nofree nosync nounwind willreturn }
attributes #2 = { argmemonly nofree nosync nounwind willreturn }
=======
<<<<<<< HEAD
declare void @subkernel_send_message(i32, { i8*, i32 }*, i8**) local_unnamed_addr

; Function Attrs: argmemonly nounwind willreturn
declare void @llvm.lifetime.start.p0i8(i64 immarg, i8* nocapture) #1

; Function Attrs: argmemonly nounwind willreturn
declare void @llvm.lifetime.end.p0i8(i64 immarg, i8* nocapture) #1

attributes #0 = { uwtable }
attributes #1 = { argmemonly nounwind willreturn }
=======
; Function Attrs: inaccessiblememonly
declare void @rtio_output(i32, i32) local_unnamed_addr #1

attributes #0 = { uwtable }
attributes #1 = { inaccessiblememonly }
>>>>>>> 76594e85a (don't waste time and bandwidth with returning Nones)
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
<<<<<<< HEAD
!9 = !DILocation(line: 6, column: 4, scope: !10, inlinedAt: !12)
!10 = distinct !DISubprogram(name: "_Z45artiq_run_test_subkernel_opt_fn.non_self_argszz", linkageName: "_Z45artiq_run_test_subkernel_opt_fn.non_self_argszz", scope: !11, file: !11, line: 5, type: !6, scopeLine: 5, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!11 = !DIFile(filename: "test_subkernel_opt_fn.py", directory: "")
!12 = distinct !DILocation(line: 1, scope: !5)
!13 = !DILocation(line: 1, scope: !5)
!14 = !DILocation(line: 5, scope: !10, inlinedAt: !12)
!15 = !DILocation(line: 6, column: 11, scope: !10, inlinedAt: !12)
=======
<<<<<<< HEAD
!9 = !DILocation(line: 17, column: 8, scope: !10, inlinedAt: !12)
!10 = distinct !DISubprogram(name: "_Z48artiq_run_test_subkernel.DMAPulses.simple_returnzz", linkageName: "_Z48artiq_run_test_subkernel.DMAPulses.simple_returnzz", scope: !11, file: !11, line: 13, type: !6, scopeLine: 13, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!11 = !DIFile(filename: "test_subkernel.py", directory: "")
!12 = distinct !DILocation(line: 1, scope: !5)
!13 = !DILocation(line: 1, scope: !5)
=======
!9 = !DILocation(line: 49, column: 8, scope: !10, inlinedAt: !12)
!10 = distinct !DISubprogram(name: "_Z33artiq.coredevice.ttl.TTLOut.set_oI27artiq.coredevice.ttl.TTLOutEzz", linkageName: "_Z33artiq.coredevice.ttl.TTLOut.set_oI27artiq.coredevice.ttl.TTLOutEzz", scope: !11, file: !11, line: 48, type: !6, scopeLine: 48, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!11 = !DIFile(filename: "ttl.py", directory: "/home/spaqin/m-labs/artiq/artiq/coredevice")
!12 = distinct !DILocation(line: 57, column: 8, scope: !13, inlinedAt: !14)
!13 = distinct !DISubprogram(name: "_Z30artiq.coredevice.ttl.TTLOut.onI27artiq.coredevice.ttl.TTLOutEzz", linkageName: "_Z30artiq.coredevice.ttl.TTLOut.onI27artiq.coredevice.ttl.TTLOutEzz", scope: !11, file: !11, line: 52, type: !6, scopeLine: 52, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!14 = distinct !DILocation(line: 83, column: 8, scope: !15, inlinedAt: !16)
!15 = distinct !DISubprogram(name: "_Z33artiq.coredevice.ttl.TTLOut.pulseI27artiq.coredevice.ttl.TTLOutEzz", linkageName: "_Z33artiq.coredevice.ttl.TTLOut.pulseI27artiq.coredevice.ttl.TTLOutEzz", scope: !11, file: !11, line: 78, type: !6, scopeLine: 78, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!16 = distinct !DILocation(line: 25, column: 8, scope: !17, inlinedAt: !19)
!17 = distinct !DISubprogram(name: "_Z46artiq_run_test_subkernel.DMAPulses.simple_selfzz", linkageName: "_Z46artiq_run_test_subkernel.DMAPulses.simple_selfzz", scope: !18, file: !18, line: 24, type: !6, scopeLine: 24, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!18 = !DIFile(filename: "test_subkernel.py", directory: "")
!19 = distinct !DILocation(line: 1, scope: !5)
!20 = !DILocation(line: 84, column: 8, scope: !15, inlinedAt: !16)
!21 = !DILocation(line: 49, column: 8, scope: !10, inlinedAt: !22)
!22 = distinct !DILocation(line: 65, column: 8, scope: !23, inlinedAt: !24)
!23 = distinct !DISubprogram(name: "_Z31artiq.coredevice.ttl.TTLOut.offI27artiq.coredevice.ttl.TTLOutEzz", linkageName: "_Z31artiq.coredevice.ttl.TTLOut.offI27artiq.coredevice.ttl.TTLOutEzz", scope: !11, file: !11, line: 60, type: !6, scopeLine: 60, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!24 = distinct !DILocation(line: 85, column: 8, scope: !15, inlinedAt: !16)
!25 = !DILocation(line: 1, scope: !5)
>>>>>>> 76594e85a (don't waste time and bandwidth with returning Nones)
>>>>>>> ff18ac7b5 (don't waste time and bandwidth with returning Nones)
