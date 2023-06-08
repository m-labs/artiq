; ModuleID = '<string>'
source_filename = "<string>"
target datalayout = "e-m:e-p:32:32-i64:64-n32-S128"
target triple = "riscv32-unknown-linux"

@S.i = private unnamed_addr constant [2 x i8] c"i:"

; Function Attrs: uwtable
define void @__modinit__(i8* nocapture readnone %.1) local_unnamed_addr #0 personality i32 (...)* @__artiq_personality !dbg !5 {
entry:
  %.15.i = alloca { i8*, i32 }, align 8, !dbg !9
  %subkernel.return.i = alloca i8*, align 4, !dbg !9
  %subkernel.retval.i = alloca i32, align 4, !dbg !9
  %subkernel.await.args = call i8 @subkernel_await_message(i32 0, i64 10000, i8 2, i8 3), !dbg !13
  %subkernel.arg.stack = call i8* @llvm.stacksave(), !dbg !13
  %rpc.ret.alloc.twoja = alloca i32, align 4, !dbg !13
  %rpc.ret.ptr.twoja = bitcast i32* %rpc.ret.alloc.twoja to i8*, !dbg !13
  br label %rpc.head.twoja, !dbg !13

rpc.head.twoja:                                   ; preds = %rpc.continue.twoja, %entry
  %rpc.ptr.twoja = phi i8* [ %rpc.ret.ptr.twoja, %entry ], [ %rpc.alloc.twoja, %rpc.continue.twoja ], !dbg !13
  %rpc.size.next.twoja = call i32 @rpc_recv(i8* %rpc.ptr.twoja), !dbg !13
  %rpc.done.twoja = icmp eq i32 %rpc.size.next.twoja, 0, !dbg !13
  br i1 %rpc.done.twoja, label %rpc.tail.twoja, label %rpc.continue.twoja, !dbg !13

rpc.continue.twoja:                               ; preds = %rpc.head.twoja
  %rpc.alloc.twoja = alloca i8, i32 %rpc.size.next.twoja, align 8, !dbg !13
  br label %rpc.head.twoja, !dbg !13

rpc.tail.twoja:                                   ; preds = %rpc.head.twoja
  %rpc.ret.twoja = load i32, i32* %rpc.ret.alloc.twoja, align 4, !dbg !13
  call void @llvm.stackrestore(i8* %subkernel.arg.stack), !dbg !13
  %.12 = icmp ugt i8 %subkernel.await.args, 2, !dbg !13
  br i1 %.12, label %optarg.get.b, label %optarg.tail.b, !dbg !13

optarg.get.b:                                     ; preds = %rpc.tail.twoja
  %subkernel.arg.stack.1 = call i8* @llvm.stacksave(), !dbg !13
  %rpc.ret.alloc.b = alloca i32, align 4, !dbg !13
  %rpc.ret.ptr.b = bitcast i32* %rpc.ret.alloc.b to i8*, !dbg !13
  br label %rpc.head.b, !dbg !13

rpc.head.b:                                       ; preds = %rpc.continue.b, %optarg.get.b
  %rpc.ptr.b = phi i8* [ %rpc.ret.ptr.b, %optarg.get.b ], [ %rpc.alloc.b, %rpc.continue.b ], !dbg !13
  %rpc.size.next.b = call i32 @rpc_recv(i8* %rpc.ptr.b), !dbg !13
  %rpc.done.b = icmp eq i32 %rpc.size.next.b, 0, !dbg !13
  br i1 %rpc.done.b, label %rpc.tail.b, label %rpc.continue.b, !dbg !13

rpc.continue.b:                                   ; preds = %rpc.head.b
  %rpc.alloc.b = alloca i8, i32 %rpc.size.next.b, align 8, !dbg !13
  br label %rpc.head.b, !dbg !13

rpc.tail.b:                                       ; preds = %rpc.head.b
  %rpc.ret.b = load i32, i32* %rpc.ret.alloc.b, align 4, !dbg !13
  call void @llvm.stackrestore(i8* %subkernel.arg.stack.1), !dbg !13
  br label %optarg.tail.b, !dbg !13

optarg.tail.b:                                    ; preds = %rpc.tail.b, %rpc.tail.twoja
  %DEF.b.i = phi i32 [ %rpc.ret.b, %rpc.tail.b ], [ 5, %rpc.tail.twoja ], !dbg !13
  %0 = bitcast { i8*, i32 }* %.15.i to i8*, !dbg !14
  call void @llvm.lifetime.start.p0i8(i64 8, i8* nonnull %0), !dbg !14
  %1 = bitcast i8** %subkernel.return.i to i8*, !dbg !14
  call void @llvm.lifetime.start.p0i8(i64 4, i8* nonnull %1), !dbg !14
  %2 = bitcast i32* %subkernel.retval.i to i8*, !dbg !14
  call void @llvm.lifetime.start.p0i8(i64 4, i8* nonnull %2), !dbg !14
  %UNN.5.i = add i32 %DEF.b.i, %rpc.ret.twoja, !dbg !15
  %.15.repack.i = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.15.i, i32 0, i32 0, !dbg !9
  store i8* getelementptr inbounds ([2 x i8], [2 x i8]* @S.i, i32 0, i32 0), i8** %.15.repack.i, align 8, !dbg !9
  %.15.repack1.i = getelementptr inbounds { i8*, i32 }, { i8*, i32 }* %.15.i, i32 0, i32 1, !dbg !9
  store i32 2, i32* %.15.repack1.i, align 4, !dbg !9
  store i32 %UNN.5.i, i32* %subkernel.retval.i, align 4, !dbg !9
  %3 = bitcast i8** %subkernel.return.i to i32**, !dbg !9
  store i32* %subkernel.retval.i, i32** %3, align 4, !dbg !9
  call void @subkernel_send_message(i32 0, i8 1, { i8*, i32 }* nonnull %.15.i, i8** nonnull %subkernel.return.i), !dbg !9
  call void @llvm.lifetime.end.p0i8(i64 8, i8* nonnull %0), !dbg !9
  call void @llvm.lifetime.end.p0i8(i64 4, i8* nonnull %1), !dbg !9
  call void @llvm.lifetime.end.p0i8(i64 4, i8* nonnull %2), !dbg !9
  ret void, !dbg !13
}

declare i32 @__artiq_personality(...)

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
!9 = !DILocation(line: 18, column: 8, scope: !10, inlinedAt: !12)
!10 = distinct !DISubprogram(name: "_Z50artiq_run_test_subkernel_opt.DMAPulses.simple_argszz", linkageName: "_Z50artiq_run_test_subkernel_opt.DMAPulses.simple_argszz", scope: !11, file: !11, line: 17, type: !6, scopeLine: 17, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!11 = !DIFile(filename: "test_subkernel_opt.py", directory: "")
!12 = distinct !DILocation(line: 1, scope: !5)
!13 = !DILocation(line: 1, scope: !5)
!14 = !DILocation(line: 17, column: 4, scope: !10, inlinedAt: !12)
!15 = !DILocation(line: 18, column: 15, scope: !10, inlinedAt: !12)
