; ModuleID = '<string>'
source_filename = "<string>"
target datalayout = "e-m:e-p:32:32-i64:64-n32-S128"
target triple = "riscv32-unknown-linux"

@S.i = private unnamed_addr constant [2 x i8] c"i:"

; Function Attrs: uwtable
define void @__modinit__(i8* nocapture readnone %.1) local_unnamed_addr #0 personality i32 (...)* @__artiq_personality !dbg !5 {
entry:
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
  call void @llvm.lifetime.end.p0i8(i64 8, i8* nonnull %0), !dbg !9
  call void @llvm.lifetime.end.p0i8(i64 4, i8* nonnull %1), !dbg !9
  call void @llvm.lifetime.end.p0i8(i64 4, i8* nonnull %2), !dbg !9
  ret void, !dbg !13
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
declare void @subkernel_send_message(i32, { i8*, i32 }*, i8**) local_unnamed_addr

; Function Attrs: argmemonly nounwind willreturn
declare void @llvm.lifetime.start.p0i8(i64 immarg, i8* nocapture) #1

; Function Attrs: argmemonly nounwind willreturn
declare void @llvm.lifetime.end.p0i8(i64 immarg, i8* nocapture) #1

attributes #0 = { uwtable }
attributes #1 = { argmemonly nounwind willreturn }
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
!9 = !DILocation(line: 18, column: 8, scope: !10, inlinedAt: !12)
!10 = distinct !DISubprogram(name: "_Z50artiq_run_test_subkernel_opt.DMAPulses.simple_argszz", linkageName: "_Z50artiq_run_test_subkernel_opt.DMAPulses.simple_argszz", scope: !11, file: !11, line: 17, type: !6, scopeLine: 17, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!11 = !DIFile(filename: "test_subkernel_opt.py", directory: "")
!12 = distinct !DILocation(line: 1, scope: !5)
!13 = !DILocation(line: 1, scope: !5)
!14 = !DILocation(line: 17, column: 4, scope: !10, inlinedAt: !12)
!15 = !DILocation(line: 18, column: 15, scope: !10, inlinedAt: !12)
=======
!9 = !DILocation(line: 17, column: 8, scope: !10, inlinedAt: !12)
!10 = distinct !DISubprogram(name: "_Z48artiq_run_test_subkernel.DMAPulses.simple_returnzz", linkageName: "_Z48artiq_run_test_subkernel.DMAPulses.simple_returnzz", scope: !11, file: !11, line: 13, type: !6, scopeLine: 13, spFlags: DISPFlagLocalToUnit | DISPFlagDefinition, unit: !3, retainedNodes: !8)
!11 = !DIFile(filename: "test_subkernel.py", directory: "")
!12 = distinct !DILocation(line: 1, scope: !5)
!13 = !DILocation(line: 1, scope: !5)
>>>>>>> ff18ac7b5 (don't waste time and bandwidth with returning Nones)
